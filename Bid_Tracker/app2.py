import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import time
import json
from database import Database
import requests
import gspread
from google.oauth2 import service_account

# Initialize database
db = Database()

def format_sheet_name(project_name):
    """Format project name to be valid as a sheet name"""
    # Remove invalid characters and limit length
    valid_name = "".join(c for c in project_name if c.isalnum() or c in " -_")
    return valid_name[:31]  # Sheets names limited to 31 chars

# Add to session state initialization at the top
if 'project_locations' not in st.session_state:
    st.session_state.project_locations = {}
if 'project_checklists' not in st.session_state:
    st.session_state.project_checklists = {}

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

# Add caching for spreadsheet data
if 'cache' not in st.session_state:
    st.session_state.cache = {
        'spreadsheet': None,
        'last_refresh': None,
        'materials': None,
        'materials_last_refresh': None
    }

# Set page config for mobile
st.set_page_config(
    page_title="Bid Tracker",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

try:
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

def get_or_create_spreadsheet(sheets_client):
    SPREADSHEET_NAME = "Bid Results Tracker"
    try:
        # Try to find existing spreadsheet by name
        spreadsheet_list = sheets_client.list_spreadsheet_files()
        for spreadsheet in spreadsheet_list:
            if spreadsheet['name'] == SPREADSHEET_NAME:
                return sheets_client.open_by_key(spreadsheet['id'])
        
        # If not found, create new spreadsheet
        spreadsheet = sheets_client.create(SPREADSHEET_NAME)
        
        # Set up Master Sheet
        master_sheet = spreadsheet.sheet1
        master_sheet.update_title("Master Sheet")
        headers = ["Date", "Contractor", "Project Name", "Project Owner", 
                  "Location", "Unit Number", "Material", "Unit", 
                  "Quantity", "Price", "Total"]
        master_sheet.append_row(headers)
        
        # Set up Materials Sheet
        materials_sheet = spreadsheet.add_worksheet("Materials", 1000, 2)
        materials_sheet.append_row(["Material", "Unit"])
        
        # Share with your email
        spreadsheet.share(
            'mannysconcretenj@gmail.com',
            perm_type='user',
            role='writer'
        )
        
        st.success(f"Created new spreadsheet: {SPREADSHEET_NAME}")
        return spreadsheet
        
    except Exception as e:
        st.error(f"Error with spreadsheet: {str(e)}")
        return None

def get_spreadsheet(sheets_client):
    try:
        # Use cached spreadsheet if available and less than 1 minute old
        if (st.session_state.cache['spreadsheet'] and 
            st.session_state.cache['last_refresh'] and 
            datetime.now() - st.session_state.cache['last_refresh'] < timedelta(minutes=1)):
            return st.session_state.cache['spreadsheet']
            
        # Use the permanent spreadsheet ID
        SPREADSHEET_ID = "1_VpKh9Ha-43jUFeYyVljAmSCszay_ChD9jiWAbW_jEU"
        
        try:
            time.sleep(1)  # Add delay to prevent quota issues
            spreadsheet = sheets_client.open_by_key(SPREADSHEET_ID)
            
            # Update cache
            st.session_state.cache['spreadsheet'] = spreadsheet
            st.session_state.cache['last_refresh'] = datetime.now()
            
            return spreadsheet
        except Exception as e:
            if "429" in str(e):
                st.error("Rate limit reached. Please wait a moment and try again.")
            else:
                st.error(f"Error opening spreadsheet: {str(e)}")
            return None
            
    except Exception as e:
        st.error(f"Error with spreadsheet: {str(e)}")
        return None

def get_google_services():
    """Initialize Google services"""
    try:
        credentials = service_account.Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive.file",
            ],
        )
        
        client = gspread.authorize(credentials)
        spreadsheet = client.open_by_key(st.secrets["spreadsheet_id"])
        return None, client, spreadsheet
    except Exception as e:
        st.error(f"Error connecting to Google services: {str(e)}")
        return None, None, None

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
        time.sleep(1)  # Add delay before saving
        
        # Always save to Master Sheet
        master_sheet = spreadsheet.worksheet("Master Sheet")
        master_sheet.append_row([
            data[0],  # Date
            data[1],  # Contractor
            data[2],  # Project Name
            data[3],  # Project Owner
            data[4],  # Location
            data[5],  # Unit Number
            data[6],  # Material
            data[7],  # Unit
            data[8],  # Quantity
            data[9],  # Price
            data[10]  # Total
        ])
        
        time.sleep(1)  # Add delay between operations
        
        # Get or create project-specific sheet
        try:
            project_sheet = spreadsheet.worksheet(project_name)
        except:
            time.sleep(1)  # Add delay before creating new sheet
            project_sheet = spreadsheet.add_worksheet(project_name, 1000, 20)
            headers = ["Date", "Contractor", "Location", "Unit Number",
                      "Material", "Unit", "Quantity", "Price", "Total"]
            project_sheet.append_row(headers)
        
        time.sleep(1)  # Add delay before final save
        
        # Format data for project sheet
        project_data = [
            data[0],  # Date
            data[1],  # Contractor
            data[4],  # Location
            data[5],  # Unit Number
            data[6],  # Material
            data[7],  # Unit
            data[8],  # Quantity
            data[9],  # Price
            data[10]  # Total
        ]
        project_sheet.append_row(project_data)
        
        # Clear cache to force refresh
        st.session_state.cache['spreadsheet'] = None
        st.session_state.cache['materials'] = None
        
        st.success("Bid saved successfully!")
        
    except Exception as e:
        if "429" in str(e):
            st.error("Rate limit reached. Please wait a moment and try again.")
        else:
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

def get_or_create_materials_sheet(spreadsheet):
    try:
        # Try to get Materials sheet
        try:
            materials_sheet = spreadsheet.worksheet("Materials")
        except:
            # Create Materials sheet if it doesn't exist
            materials_sheet = spreadsheet.add_worksheet("Materials", 1000, 2)
            materials_sheet.append_row(["Material", "Unit"])
            # Add some default materials
            default_materials = [
                ["Concrete sidewalk 4\"", "SF"],
                ["Concrete apron 6\"", "SF"],
                ["Belgian block", "LF"],
                ["Concrete curb", "LF"]
            ]
            materials_sheet.append_rows(default_materials)
        return materials_sheet
    except Exception as e:
        st.error(f"Error with materials sheet: {str(e)}")
        return None

def get_materials_from_sheet(spreadsheet):
    try:
        # Use cached materials if available and less than 5 minutes old
        if (st.session_state.cache['materials'] and 
            st.session_state.cache['materials_last_refresh'] and 
            datetime.now() - st.session_state.cache['materials_last_refresh'] < timedelta(minutes=5)):
            return st.session_state.cache['materials']
            
        time.sleep(1)  # Add delay to prevent quota issues
        materials_sheet = get_or_create_materials_sheet(spreadsheet)
        if not materials_sheet:
            return {}
            
        # Get all data from the Materials sheet
        all_data = materials_sheet.get_all_values()
        
        # Skip header row and create list of materials
        materials_data = []
        for row in all_data[1:]:  # Skip header row
            if row and len(row) >= 2 and row[0].strip():  # Check for valid rows
                materials_data.append({
                    'Material': row[0].strip(),
                    'Unit': row[1].strip() if len(row) > 1 and row[1].strip() else 'SF'
                })
        
        # Update cache
        st.session_state.cache['materials'] = materials_data
        st.session_state.cache['materials_last_refresh'] = datetime.now()
        
        return materials_data
    except Exception as e:
        st.error(f"Error getting materials: {str(e)}")
        return {}

def get_material_stats(spreadsheet):
    try:
        master_sheet = spreadsheet.worksheet("Master Sheet")
        data = master_sheet.get_all_records()
        
        # Calculate averages by material
        material_stats = {}
        for row in data:
            material = str(row['Material']).strip()
            if not material:
                continue
                
            unit = row['Unit']
            try:
                price = float(str(row['Price']).replace('$', '').replace(',', ''))
            except (ValueError, TypeError):
                continue
            
            if material not in material_stats:
                material_stats[material] = {
                    'units': set([unit]),
                    'prices': [price],
                    'total_price': price,
                    'count': 1,
                    'default_unit': unit
                }
            else:
                stats = material_stats[material]
                stats['units'].add(unit)
                stats['prices'].append(price)
                stats['total_price'] += price
                stats['count'] += 1
        
        # Calculate averages
        for material in material_stats:
            stats = material_stats[material]
            stats['avg_price'] = stats['total_price'] / stats['count']
            stats['most_common_unit'] = max(stats['units'], 
                                          key=lambda x: sum(1 for row in data 
                                          if row['Material'] == material and row['Unit'] == x))
            
        return material_stats
    except Exception as e:
        st.error(f"Error calculating material stats: {str(e)}")
        return {}

def add_new_material(spreadsheet, material_name, unit='SF'):
    try:
        time.sleep(1)  # Add delay before operation
        materials_sheet = get_or_create_materials_sheet(spreadsheet)
        if not materials_sheet:
            return False
            
        # Check if material already exists
        materials_data = materials_sheet.get_all_records()
        if any(row['Material'] == material_name for row in materials_data):
            st.warning(f"Material '{material_name}' already exists")
            return False
            
        # Add new material
        materials_sheet.append_row([material_name, unit])
        
        # Clear materials cache to force refresh
        st.session_state.cache['materials'] = None
        
        st.success(f"Added new material: {material_name}")
        return True
    except Exception as e:
        st.error(f"Error adding material: {str(e)}")
        return False

def display_bid_history(spreadsheet, project_name):
    """Display bid history for a project"""
    try:
        sheet_name = format_sheet_name(project_name)
        worksheet = spreadsheet.worksheet(sheet_name)
        records = worksheet.get_all_records()
        
        if records:
            df = pd.DataFrame(records)
            st.dataframe(df)
        else:
            st.info("No bid history found for this project")
    except Exception as e:
        st.info("No bid history available for this project yet")

def create_new_project(spreadsheet, project_name, owner_name):
    try:
        # Format sheet name to include owner
        sheet_name = f"{project_name} - {owner_name}"
        
        # Check if project already exists
        try:
            existing_sheet = spreadsheet.worksheet(sheet_name)
            st.error(f"Project '{project_name}' already exists!")
            return False
        except:
            # Create new project sheet
            time.sleep(1)  # Add delay before creating sheet
            project_sheet = spreadsheet.add_worksheet(sheet_name, 1000, 20)
            headers = ["Date", "Contractor", "Location", "Unit Number",
                      "Material", "Unit", "Quantity", "Price", "Total"]
            project_sheet.append_row(headers)
            
            # Add to database
            db.add_project(project_name, owner_name)
            
            st.success(f"Created new project: {project_name} for {owner_name}")
            return True
            
    except Exception as e:
        st.error(f"Error creating project: {str(e)}")
        return False

def project_tracking_dashboard(spreadsheet):
    st.header("Project Tracking")
    
    worksheet = spreadsheet.worksheet("Master Sheet")
    data = worksheet.get_all_records()
    
    if data:
        df = pd.DataFrame(data)
        
        # Group by Project Name
        projects = df['Project Name'].unique()
        selected_project = st.selectbox("Select Project", projects)
        
        if selected_project:
            project_data = df[df['Project Name'] == selected_project]
            
            st.subheader("Project Details")
            st.write(f"Project Owner: {project_data['Project Owner'].iloc[0]}")
            st.write(f"Location: {project_data['Location'].iloc[0]}")
            
            st.subheader("Bid Items")
            bid_items = project_data[['Material', 'Unit', 'Quantity', 'Price', 'Total']]
            st.dataframe(bid_items)
            
            total_bid = project_data['Total'].sum()
            st.write(f"Total Project Bid: ${total_bid:,.2f}")
    else:
        st.info("No projects available for tracking")

def get_coordinates(address):
    try:
        # Using OpenStreetMap Nominatim API (no key required)
        url = f"https://nominatim.openstreetmap.org/search?q={address}&format=json&limit=1"
        headers = {'User-Agent': 'BidTracker/1.0'}
        response = requests.get(url, headers=headers)
        data = response.json()
        
        if data:
            return float(data[0]['lat']), float(data[0]['lon'])
        return None, None
    except Exception as e:
        st.error(f"Error geocoding address: {str(e)}")
        return None, None

def project_status_dashboard(spreadsheet):
    st.header("Project Status")
    
    worksheet = spreadsheet.worksheet("Master Sheet")
    data = worksheet.get_all_records()
    
    if data:
        df = pd.DataFrame(data)
        
        st.subheader("Project Summary")
        project_summary = df.groupby('Project Name')['Total'].sum().reset_index()
        project_summary.columns = ['Project Name', 'Total Bid Amount']
        st.dataframe(project_summary)
        
        # Project count and total value
        total_projects = len(df['Project Name'].unique())
        total_value = df['Total'].sum()
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Projects", total_projects)
        with col2:
            st.metric("Total Value", f"${total_value:,.2f}")
    else:
        st.info("No project status data available")

def load_bid_history():
    """Load bid history from the database"""
    return db.get_bids() or []

def save_bid(bid_data):
    """Save bid to the database"""
    db.add_bid(bid_data)

def bid_entry_page(spreadsheet):
    st.header("Bid Entry")
    
    # Get materials from the Materials sheet
    materials_sheet = spreadsheet.worksheet("Materials")
    materials_data = materials_sheet.get_all_records()
    materials_list = [item.get('Material', '') for item in materials_data if item.get('Material')]
    
    # Load bid history
    bid_history = load_bid_history()
    
    # Create columns for form and history
    col1, col2 = st.columns([2, 1])
    
    with col1:
        worksheet = spreadsheet.worksheet("Master Sheet")
        
        # Create the form
        with st.form("bid_entry_form"):
            date = st.date_input("Date", datetime.today())
            contractor = st.text_input("Contractor", value="Manny's Concrete NJ")
            project_name = st.text_input("Project Name")
            project_owner = st.text_input("Project Owner")
            location = st.text_input("Location")
            unit_number = st.text_input("Unit Number")
            
            # Use dropdown for materials
            material = st.selectbox("Material", options=materials_list)
            
            # Get default unit based on selected material
            default_unit = next((item.get('Unit', '') for item in materials_data if item.get('Material') == material), '')
            unit = st.text_input("Unit", value=default_unit)
            
            quantity = st.number_input("Quantity", min_value=0.0, format="%f")
            price = st.number_input("Price per Unit", min_value=0.0, format="%f")
            
            # Calculate total
            total = quantity * price
            st.write(f"Total: ${total:,.2f}")
            
            submitted = st.form_submit_button("Submit Bid")
            
            if submitted:
                # Prepare the bid data
                bid_data = {
                    "date": date.strftime("%Y-%m-%d"),
                    "contractor": contractor,
                    "project_name": project_name,
                    "project_owner": project_owner,
                    "location": location,
                    "unit_number": unit_number,
                    "material": material,
                    "unit": unit,
                    "quantity": quantity,
                    "price": price,
                    "total": total
                }
                
                # Save to database
                save_bid(bid_data)
                
                # Save to Google Sheet
                row_data = [
                    date.strftime("%Y-%m-%d"),
                    contractor,
                    project_name,
                    project_owner,
                    location,
                    unit_number,
                    material,
                    unit,
                    quantity,
                    price,
                    total,
                    ""  # Empty column at the end
                ]
                
                try:
                    worksheet.append_row(row_data)
                    st.success("Bid successfully added!")
                    time.sleep(0.5)  # Brief pause for the success message
                    st.experimental_rerun()  # Refresh to show updated history
                except Exception as e:
                    st.error(f"Error adding bid: {str(e)}")
    
    with col2:
        st.subheader("Recent Bids")
        if bid_history:
            for bid in reversed(bid_history[-5:]):  # Show last 5 bids
                with st.expander(f"{bid['project_name']} - {bid['date']}"):
                    st.write(f"Project Owner: {bid['project_owner']}")
                    st.write(f"Location: {bid['location']}")
                    st.write(f"Material: {bid['material']}")
                    st.write(f"Quantity: {bid['quantity']} {bid['unit']}")
                    st.write(f"Price: ${bid['price']:.2f}")
                    st.write(f"Total: ${bid['total']:.2f}")
        else:
            st.info("No bid history available")

def main():
    st.title("📊 Bid Tracker")
    
    # Initialize Google services and get spreadsheet
    _, sheets_client, spreadsheet = get_google_services()
    if not spreadsheet:
        st.error("Failed to initialize Google services. Please check your credentials.")
        return
        
    # Add navigation
    page = st.sidebar.radio("Navigation", ["Bid Entry", "Project Tracking"])
    
    if page == "Bid Entry":
        bid_entry_page(spreadsheet)
    elif page == "Project Tracking":
        project_tracking_dashboard(spreadsheet)

if __name__ == "__main__":
    main()
