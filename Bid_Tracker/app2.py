import streamlit as st
from database import Database
import pandas as pd
from datetime import datetime
import os

# Initialize database
db = Database()

# Initialize session state
if 'materials' not in st.session_state:
    st.session_state.materials = set()
if 'profile' not in st.session_state:
    st.session_state.profile = {
        'project_name': '',
        'project_owner': '',
    }
if 'contractors' not in st.session_state:
    st.session_state.contractors = {}

# Set page config for mobile
st.set_page_config(
    page_title="Bid Tracker",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

try:
    import gspread
    from google.oauth2.service_account import Credentials
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
except ImportError:
    st.error("""
        Missing required packages. Please run:
        pip install gspread google-auth google-api-python-client
    """)
    st.stop()

# Google API configuration
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/drive.file'
]

# Default units
DEFAULT_UNITS = ["SF", "SY", "LF", "Unit"]

def initialize_session_state():
    if 'profile' not in st.session_state:
        st.session_state.profile = {
            'project_name': '',
            'project_owner': '',
        }
    if 'materials' not in st.session_state:
        st.session_state.materials = set()
    if 'contractors' not in st.session_state:
        st.session_state.contractors = {}
    if 'projects' not in st.session_state:
        st.session_state.projects = {}  # {project_name: {'owner': owner}}

def save_project_profile(project_name, project_owner):
    st.session_state.projects[project_name] = {
        'owner': project_owner
    }

def get_project_details(project_name):
    return st.session_state.projects.get(project_name, {'owner': ''})

def save_contractor_profile(contractor_name, location):
    st.session_state.contractors[contractor_name] = location
    
def get_contractor_location(contractor_name):
    return st.session_state.contractors.get(contractor_name, '')

def get_google_services():
    try:
        # First, check if we can access secrets
        if 'gcp_service_account' not in st.secrets:
            st.error("No GCP service account secrets found")
            return None, None
            
        # Create credentials dict from secrets
        credentials_dict = st.secrets["gcp_service_account"]
        
        # Debug: Show service account email
        st.info(f"Using service account: {credentials_dict['client_email']}")
        
        credentials = service_account.Credentials.from_service_account_info(
            credentials_dict,
            scopes=SCOPES
        )
        
        drive_service = build('drive', 'v3', credentials=credentials)
        sheets_client = gspread.authorize(credentials)
        return drive_service, sheets_client
    except Exception as e:
        st.error(f"Credentials Error: {str(e)}")
        st.error("Please check your secrets configuration")
        return None, None

def create_and_share_spreadsheet(drive_service, sheets_client):
    try:
        SPREADSHEET_NAME = "Bid Results Tracker"
        
        # Try to find existing spreadsheet first
        try:
            spreadsheet_list = sheets_client.list_spreadsheet_files()
            for spreadsheet in spreadsheet_list:
                if spreadsheet['name'] == SPREADSHEET_NAME:
                    return sheets_client.open_by_key(spreadsheet['id'])
        except Exception as e:
            st.warning(f"Searching for existing spreadsheet: {str(e)}")
        
        # If not found, create new spreadsheet
        spreadsheet = sheets_client.create(SPREADSHEET_NAME)
        worksheet = spreadsheet.sheet1
        worksheet.update_title("Master Sheet")
        
        # Set up headers for master sheet
        headers = ["Date", "Contractor", "Project Name", "Project Owner", 
                  "Location", "Unit Number", "Material", "Unit", 
                  "Quantity", "Price", "Total"]
        worksheet.append_row(headers)
        
        # Share with your email
        spreadsheet.share(
            'mannysconcretenj@gmail.com',
            perm_type='user',
            role='writer'
        )
        
        st.success(f"Created new master spreadsheet: {SPREADSHEET_NAME}")
        return spreadsheet
        
    except Exception as e:
        st.error(f"Error with spreadsheet: {str(e)}")
        return None

def delete_row(spreadsheet, sheet_name, row_index):
    try:
        # Delete from project sheet
        project_sheet = spreadsheet.worksheet(sheet_name)
        project_sheet.delete_rows(row_index + 2)  # +2 for header and 1-based index
        
        # Find and delete corresponding row in master sheet
        master_sheet = spreadsheet.worksheet("Master Sheet")
        master_data = master_sheet.get_all_records()
        
        # Get the data from the deleted project row
        project_data = project_sheet.get_all_records()
        deleted_row = project_data[row_index - 1]  # -1 because row_index is 1-based
        
        # Find matching row in master sheet
        for i, row in enumerate(master_data):
            if (row['Date'] == deleted_row['Date'] and 
                row['Contractor'] == deleted_row['Contractor'] and
                row['Total'] == deleted_row['Total']):
                master_sheet.delete_rows(i + 2)  # +2 for header and 1-based index
                break
        
        return True
    except Exception as e:
        st.error(f"Error deleting row: {str(e)}")
        return False

def save_to_sheets(spreadsheet, data, project_name):
    try:
        # Always save to Master Sheet
        master_sheet = spreadsheet.worksheet("Master Sheet")
        master_sheet.append_row(data)
        
        # Get or create project-specific sheet
        try:
            project_sheet = spreadsheet.worksheet(project_name)
        except:
            project_sheet = spreadsheet.add_worksheet(project_name, 1000, 20)
            headers = ["Date", "Contractor", "Location", "Unit Number",
                      "Material", "Unit", "Quantity", "Price", "Total"]
            project_sheet.append_row(headers)
        
        # Format data for project sheet
        project_data = [
            data[0],  # Date
            data[1],  # Contractor
            data[5],  # Location
            data[6],  # Unit Number
            data[7],  # Material
            data[8],  # Unit
            data[9],  # Quantity
            data[10], # Price
            data[11]  # Total
        ]
        project_sheet.append_row(project_data)
        st.success("Bid saved successfully to both Master Sheet and Project Sheet!")
        
    except Exception as e:
        st.error(f"Error saving bid: {str(e)}")

def calculate_contractor_totals(data):
    contractor_totals = {}
    for row in data:
        contractor = row['Contractor']
        try:
            total = float(str(row['Total']).replace('$', '').replace(',', ''))
            contractor_totals[contractor] = contractor_totals.get(contractor, 0) + total
        except (ValueError, KeyError):
            continue
    return contractor_totals

def format_currency(amount):
    return f"${amount:,.2f}"

def share_spreadsheet(drive_service, spreadsheet):
    try:
        spreadsheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet.id}"
        spreadsheet.share(
            'mannysconcretenj@gmail.com',
            perm_type='user',
            role='writer',
            notify=True,
            email_message=f'Your Bid Results Tracker spreadsheet has been shared with you.\n\nAccess it here: {spreadsheet_url}'
        )
        st.success(f"""Spreadsheet shared successfully! Check your email.
                   \nOr access it directly: {spreadsheet_url}""")
    except Exception as e:
        st.error(f"Error sharing spreadsheet: {str(e)}")

def get_material_averages(spreadsheet):
    try:
        master_sheet = spreadsheet.worksheet("Master Sheet")
        data = master_sheet.get_all_records()
        
        # Calculate averages by material
        material_stats = {}
        for row in data:
            material = row['Material']
            unit = row['Unit']
            price = float(str(row['Price']).replace('$', '').replace(',', ''))
            
            if material not in material_stats:
                material_stats[material] = {
                    'units': set(),
                    'prices': [],
                    'total_price': 0,
                    'count': 0
                }
            
            material_stats[material]['units'].add(unit)
            material_stats[material]['prices'].append(price)
            material_stats[material]['total_price'] += price
            material_stats[material]['count'] += 1
        
        # Calculate averages and most common unit
        for material in material_stats:
            stats = material_stats[material]
            stats['avg_price'] = stats['total_price'] / stats['count']
            stats['most_common_unit'] = max(stats['units'], key=lambda x: sum(1 for row in data 
                                          if row['Material'] == material and row['Unit'] == x))
            
        return material_stats
    except Exception as e:
        st.error(f"Error calculating averages: {str(e)}")
        return {}

def main():
    # Debug secrets (you can remove this later)
    if st.secrets["gcp_service_account"]:
        st.write("GCP credentials found!")
    
    st.title("📊 Bid Tracker")
    
    # Initialize Google services
    drive_service, sheets_client = get_google_services()
    if not drive_service or not sheets_client:
        st.error("Failed to initialize Google services. Please check your credentials.")
        return

    spreadsheet = create_and_share_spreadsheet(drive_service, sheets_client)
    if not spreadsheet:
        st.error("Failed to access or create spreadsheet.")
        return
    
    # Mobile-friendly navigation
    page = st.radio("Navigation", ["Projects", "Contractors", "Bid Entry", "History"])
    
    if page == "Projects":
        st.markdown("### Projects")
        col1, col2 = st.columns(2)
        with col1:
            new_project_name = st.text_input("Project Name")
        with col2:
            new_project_owner = st.text_input("Project Owner")
        
        if st.button("Add Project") and new_project_name and new_project_owner:
            if db.add_project(new_project_name, new_project_owner):
                st.success(f"Added project: {new_project_name}")
            else:
                st.error("Project already exists")
        
        # Show existing projects
        projects = db.get_projects()
        if projects:
            st.markdown("### Existing Projects")
            df = pd.DataFrame(projects, columns=["Project Name", "Owner"])
            st.dataframe(df)
    
    elif page == "Contractors":
        st.markdown("### Contractors")
        col1, col2 = st.columns(2)
        with col1:
            new_contractor = st.text_input("Contractor Name")
        with col2:
            new_location = st.text_input("Location")
        
        if st.button("Add Contractor") and new_contractor and new_location:
            if db.add_contractor(new_contractor, new_location):
                st.success(f"Added contractor: {new_contractor}")
            else:
                st.error("Contractor already exists")
        
        # Show existing contractors
        contractors = db.get_contractors()
        if contractors:
            st.markdown("### Existing Contractors")
            df = pd.DataFrame(contractors, columns=["Contractor", "Location"])
            st.dataframe(df)
    
    elif page == "Bid Entry":
        st.markdown("### New Bid")
        
        # Get material averages
        material_stats = get_material_averages(spreadsheet)
        
        # Project selection
        projects = db.get_projects()
        project_names = [p[0] for p in projects]
        selected_project = st.selectbox("Select Project", project_names)
        
        if selected_project:
            contractors = db.get_contractors()
            contractor_names = [c[0] for c in contractors]
            selected_contractor = st.selectbox("Select Contractor", contractor_names)
            
            if selected_contractor:
                location = db.get_contractor_location(selected_contractor)
                st.info(f"Location: {location}")
                
                # Bid details
                col1, col2 = st.columns(2)
                with col1:
                    unit_number = st.text_input("Unit Number")
                    material = st.selectbox(
                        "Material",
                        options=list(material_stats.keys()) + ["Add New Material"]
                    )
                    if material == "Add New Material":
                        new_material = st.text_input("New Material")
                        if new_material:
                            material = new_material
                            db.add_material(new_material)
                
                with col2:
                    # Auto-suggest unit based on material
                    unit_options = ["SF", "SY", "LF", "Unit"]
                    suggested_unit = material_stats.get(material, {}).get('most_common_unit', 'SF')
                    default_index = 0  # Default to first option
                    
                    # Try to find the suggested unit in our options
                    try:
                        default_index = unit_options.index(suggested_unit)
                    except ValueError:
                        pass  # If not found, keep default index
                    
                    unit = st.selectbox(
                        "Unit",
                        options=unit_options,
                        index=default_index
                    )
                    
                    quantity = st.number_input("Quantity", min_value=0.0, step=0.1)
                    
                    # Auto-suggest price based on material
                    suggested_price = material_stats.get(material, {}).get('avg_price', 0.0)
                    if suggested_price > 0:
                        st.info(f"Average price for {material}: ${suggested_price:.2f} per {suggested_unit}")
                    
                    price = st.number_input(
                        "Price per Unit",
                        min_value=0.0,
                        step=0.01,
                        value=float(f"{suggested_price:.2f}")
                    )
                
                total = quantity * price
                st.markdown(f"### Total: ${total:,.2f}")
                
                # Show historical prices
                if material in material_stats:
                    with st.expander("View Price History"):
                        stats = material_stats[material]
                        st.write(f"Price Statistics for {material}:")
                        st.write(f"Average: ${stats['avg_price']:.2f}")
                        st.write(f"Lowest: ${min(stats['prices']):.2f}")
                        st.write(f"Highest: ${max(stats['prices']):.2f}")
                        st.write(f"Most common unit: {stats['most_common_unit']}")
                
                # Submit bid
                if st.button("Submit Bid"):
                    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    data = [
                        date, selected_contractor,
                        selected_project, db.get_project_owner(selected_project),
                        location, unit_number,
                        material, unit, quantity, price, total
                    ]
                    save_to_sheets(spreadsheet, data, selected_project)
    
    elif page == "History":
        st.markdown("### Bid History")
        try:
            worksheet_list = spreadsheet.worksheets()
            project_sheets = [sheet.title for sheet in worksheet_list if sheet.title != "Master Sheet"]
            
            if project_sheets:
                selected_project = st.selectbox(
                    "Select Project to View",
                    options=project_sheets
                )
                
                sheet = spreadsheet.worksheet(selected_project)
                data = sheet.get_all_records()
                
                if data:
                    # Calculate and display contractor totals
                    st.markdown("### Project Totals by Contractor")
                    contractor_totals = calculate_contractor_totals(data)
                    
                    # Display totals in columns
                    cols = st.columns(len(contractor_totals) + 1)
                    
                    # Display individual contractor totals
                    grand_total = 0
                    for idx, (contractor, total) in enumerate(contractor_totals.items()):
                        with cols[idx]:
                            st.metric(
                                label=contractor,
                                value=f"${total:,.2f}"
                            )
                        grand_total += total
                    
                    # Display grand total
                    with cols[-1]:
                        st.metric(
                            label="GRAND TOTAL",
                            value=f"${grand_total:,.2f}"
                        )
                    
                    # Display bid history
                    st.markdown("### Detailed Bid History")
                    df = pd.DataFrame(data)
                    st.dataframe(df)
                    
                    # Delete functionality
                    row_to_delete = st.number_input(
                        "Row to Delete",
                        min_value=1,
                        max_value=len(data),
                        value=1
                    )
                    if st.button("Delete Selected Row"):
                        if delete_row(spreadsheet, selected_project, row_to_delete):
                            st.success(f"Row {row_to_delete} deleted successfully!")
                            st.rerun()
                else:
                    st.info("No bid history found for this project.")
            else:
                st.info("No projects found. Add your first bid to create a project sheet.")
                
        except Exception as e:
            st.error(f"Error loading historical data: {str(e)}")

    # Add Share Button in sidebar
    with st.sidebar:
        st.markdown("### Spreadsheet Actions")
        if st.button("📧 Share Spreadsheet to Email"):
            share_spreadsheet(drive_service, spreadsheet)

if __name__ == "__main__":
    main()
