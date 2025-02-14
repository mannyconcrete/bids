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
        sheet_name = "Bid Results Tracker"
        try:
            spreadsheet = sheets_client.open(sheet_name)
        except:
            spreadsheet = sheets_client.create(sheet_name)
            worksheet = spreadsheet.sheet1
            worksheet.update_title("Master Sheet")
            headers = ["Date", "Contractor", "Project Name", "Project Owner", 
                      "Location", "Unit Number", "Material", "Unit", 
                      "Quantity", "Price", "Total"]
            worksheet.append_row(headers)
        return spreadsheet
    except Exception as e:
        st.error(f"Error creating spreadsheet: {str(e)}")
        return None

def delete_row(spreadsheet, sheet_name, row_index):
    try:
        sheet = spreadsheet.worksheet(sheet_name)
        sheet.delete_rows(row_index + 2)  # +2 for header and 1-based index
        return True
    except Exception as e:
        st.error(f"Error deleting row: {str(e)}")
        return False

def save_to_sheets(spreadsheet, data, project_name):
    try:
        # Save to Master Sheet
        master_sheet = spreadsheet.sheet1
        master_sheet.append_row(data)
        
        # Create or update project sheet
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
        st.success("Bid saved successfully!")
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
        
        # Project selection
        projects = db.get_projects()
        project_names = [p[0] for p in projects]
        selected_project = st.selectbox("Select Project", project_names)
        
        if selected_project:
            # Contractor selection
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
                        options=db.get_materials() + ["Add New Material"]
                    )
                    if material == "Add New Material":
                        material = st.text_input("New Material")
                        if material:
                            db.add_material(material)
                
                with col2:
                    unit = st.selectbox("Unit", ["SF", "SY", "LF", "Unit"])
                    quantity = st.number_input("Quantity", min_value=0.0, step=0.1)
                    price = st.number_input("Price per Unit", min_value=0.0, step=0.01)
                
                total = quantity * price
                st.markdown(f"### Total: ${total:,.2f}")
                
                # Submit bid
                if st.button("Submit Bid"):
                    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    data = [
                        date, selected_contractor,
                        selected_project, db.get_project_owner(selected_project),
                        selected_contractor, location, unit_number,
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
