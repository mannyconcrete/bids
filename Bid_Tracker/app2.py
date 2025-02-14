import streamlit as st
from database import Database
import pandas as pd
from datetime import datetime, timedelta
import os
import time
import json

# Initialize database
db = Database()

# Initialize all session state variables at the start
if 'saved_projects' not in st.session_state:
    st.session_state.saved_projects = {}
if 'saved_contractors' not in st.session_state:
    st.session_state.saved_contractors = set()
if 'client_database' not in st.session_state:
    st.session_state.client_database = {}
if 'bid_templates' not in st.session_state:
    st.session_state.bid_templates = {}
if 'project_milestones' not in st.session_state:
    st.session_state.project_milestones = {}
if 'communication_log' not in st.session_state:
    st.session_state.communication_log = {}
if 'materials' not in st.session_state:
    st.session_state.materials = set()
if 'profile' not in st.session_state:
    st.session_state.profile = {
        'project_name': '',
        'project_owner': '',
    }
if 'contractors' not in st.session_state:
    st.session_state.contractors = {}
if 'cache' not in st.session_state:
    st.session_state.cache = {
        'spreadsheet': None,
        'last_refresh': None,
        'materials': None,
        'materials_last_refresh': None
    }
if 'project_locations' not in st.session_state:
    st.session_state.project_locations = {}
if 'project_checklists' not in st.session_state:
    st.session_state.project_checklists = {}

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
    try:
        if 'gcp_service_account' not in st.secrets:
            st.error("No GCP service account secrets found")
            return None, None, None
            
        credentials_dict = st.secrets["gcp_service_account"]
        
        credentials = service_account.Credentials.from_service_account_info(
            credentials_dict,
            scopes=SCOPES
        )
        
        drive_service = build('drive', 'v3', credentials=credentials)
        sheets_client = gspread.authorize(credentials)
        
        # Get spreadsheet using permanent ID
        spreadsheet = get_spreadsheet(sheets_client)
        
        return drive_service, sheets_client, spreadsheet
    except Exception as e:
        st.error(f"Credentials Error: {str(e)}")
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
        worksheet = spreadsheet.worksheet("Master Sheet")
        recent_bids = get_recent_bids(worksheet, project_name)
        
        if recent_bids:
            st.subheader("Recent Bids")
            for bid in reversed(recent_bids):
                with st.expander(f"{bid['Date']} - {bid['Material']}"):
                    st.write(f"Contractor: {bid['Contractor']}")
                    st.write(f"Quantity: {bid['Quantity']} {bid['Unit']}")
                    st.write(f"Price: ${bid['Price']:.2f}")
                    st.write(f"Total: ${bid['Total']:.2f}")
        else:
            st.info("No bid history available")
            
    except Exception as e:
        st.error(f"Error displaying bid history: {str(e)}")

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
    st.markdown("## 📊 Project Tracking Dashboard")
    
    # Get all projects
    projects = db.get_projects()
    if not projects:
        st.info("No projects found")
        return
        
    # Summary metrics
    total_projects = len(projects)
    active_projects = total_projects  # You can add a status field later if needed
    
    # Display summary metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Projects", total_projects)
    with col2:
        st.metric("Active Projects", active_projects)
    with col3:
        st.metric("Completed Projects", total_projects - active_projects)
    
    st.markdown("---")
    
    # Project Overview
    st.markdown("### Project Overview")
    
    # Initialize totals
    project_data = []
    
    for project_name, owner in projects:
        try:
            sheet_name = format_sheet_name(project_name)
            project_sheet = spreadsheet.worksheet(sheet_name)
            bids = project_sheet.get_all_records()
            
            if not bids:
                continue
                
            # Calculate project metrics
            total_bids = len(bids)
            total_value = sum(float(str(bid['Total']).replace('$', '').replace(',', '')) for bid in bids)
            
            # Get unique contractors
            contractors = set(bid['Contractor'] for bid in bids)
            
            # Get latest bid date
            latest_bid = max(bids, key=lambda x: x['Date'])
            latest_date = latest_bid['Date']
            
            # Calculate contractor breakdown
            contractor_totals = {}
            for bid in bids:
                contractor = bid['Contractor']
                amount = float(str(bid['Total']).replace('$', '').replace(',', ''))
                contractor_totals[contractor] = contractor_totals.get(contractor, 0) + amount
            
            # Find lowest bidder
            lowest_bidder = min(contractor_totals.items(), key=lambda x: x[1])[0]
            
            project_data.append({
                'Project': project_name,
                'Owner': owner,
                'Total Bids': total_bids,
                'Total Value': total_value,
                'Contractors': len(contractors),
                'Latest Activity': latest_date,
                'Lowest Bidder': lowest_bidder,
                'Avg Bid': total_value / total_bids if total_bids > 0 else 0
            })
            
        except Exception as e:
            st.error(f"Error processing {project_name}: {str(e)}")
    
    if project_data:
        # Convert to DataFrame
        df = pd.DataFrame(project_data)
        
        # Format currency columns
        df['Total Value'] = df['Total Value'].apply(lambda x: f"${x:,.2f}")
        df['Avg Bid'] = df['Avg Bid'].apply(lambda x: f"${x:,.2f}")
        
        # Display project table
        st.dataframe(df, use_container_width=True)
        
        # Project Details Expander
        for project in project_data:
            with st.expander(f"📋 {project['Project']} Details"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown(f"**Owner:** {project['Owner']}")
                    st.markdown(f"**Total Bids:** {project['Total Bids']}")
                    st.markdown(f"**Total Value:** {project['Total Value']}")
                
                with col2:
                    st.markdown(f"**Contractors:** {project['Contractors']}")
                    st.markdown(f"**Latest Activity:** {project['Latest Activity']}")
                    st.markdown(f"**Lowest Bidder:** {project['Lowest Bidder']}")
                
                # Get contractor breakdown for this project
                sheet_name = format_sheet_name(project['Project'])
                project_sheet = spreadsheet.worksheet(sheet_name)
                bids = project_sheet.get_all_records()
                
                contractor_data = {}
                for bid in bids:
                    contractor = bid['Contractor']
                    amount = float(str(bid['Total']).replace('$', '').replace(',', ''))
                    if contractor not in contractor_data:
                        contractor_data[contractor] = {
                            'total': amount,
                            'count': 1,
                            'avg': amount
                        }
                    else:
                        contractor_data[contractor]['total'] += amount
                        contractor_data[contractor]['count'] += 1
                        contractor_data[contractor]['avg'] = (
                            contractor_data[contractor]['total'] / 
                            contractor_data[contractor]['count']
                        )
                
                # Display contractor breakdown
                st.markdown("#### Contractor Breakdown")
                contractor_df = pd.DataFrame([
                    {
                        'Contractor': contractor,
                        'Total Bids': data['count'],
                        'Total Value': f"${data['total']:,.2f}",
                        'Average Bid': f"${data['avg']:,.2f}"
                    }
                    for contractor, data in contractor_data.items()
                ])
                st.dataframe(contractor_df, use_container_width=True)

def geocode_address(address):
    try:
        geolocator = Nominatim(user_agent="bid_tracker")
        location = geolocator.geocode(address)
        if location:
            return [location.latitude, location.longitude]
        return None
    except Exception as e:
        st.error(f"Error geocoding address: {str(e)}")
        return None

def project_status_dashboard(spreadsheet):
    st.markdown("## 📍 Project Status & Location Tracking")
    
    # Get all projects
    projects = db.get_projects()
    if not projects:
        st.info("No projects found")
        return
    
    # Project selection
    selected_project = st.selectbox(
        "Select Project",
        [p[0] for p in projects]
    )
    
    if selected_project:
        project_owner = db.get_project_owner(selected_project)
        st.info(f"Project Owner: {project_owner}")
        
        # Initialize project data in session state if not exists
        project_key = f"{selected_project} - {project_owner}"
        if project_key not in st.session_state.project_locations:
            st.session_state.project_locations[project_key] = []
        if project_key not in st.session_state.project_checklists:
            st.session_state.project_checklists[project_key] = {}
        
        # Create columns for map and location management
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Display map with all locations
            if st.session_state.project_locations[project_key]:
                locations_df = pd.DataFrame([
                    {
                        'lat': loc.get('latitude', 40.0583),
                        'lon': loc.get('longitude', -74.4057),
                        'status': loc.get('status', 'Pending')
                    }
                    for loc in st.session_state.project_locations[project_key]
                ])
                st.map(locations_df)
            else:
                # Default map centered on New Jersey
                st.map(pd.DataFrame({
                    'lat': [40.0583],
                    'lon': [-74.4057]
                }))
        
        with col2:
            # Add new location
            st.markdown("### Add Location")
            new_location = st.text_input("Location Name/Address")
            col1, col2 = st.columns(2)
            with col1:
                latitude = st.number_input("Latitude", value=40.0583, format="%.4f")
            with col2:
                longitude = st.number_input("Longitude", value=-74.4057, format="%.4f")
            
            if st.button("Add Location"):
                if new_location:
                    st.session_state.project_locations[project_key].append({
                        'address': new_location,
                        'latitude': latitude,
                        'longitude': longitude,
                        'status': 'Pending'
                    })
                    st.success(f"Added location: {new_location}")
                    st.rerun()
        
        # Location list and checklists
        st.markdown("### Project Locations")
        for idx, location in enumerate(st.session_state.project_locations[project_key]):
            with st.expander(f"📍 {location['address']}"):
                # Location coordinates
                st.markdown(f"**Coordinates:** {location.get('latitude', 40.0583):.4f}, {location.get('longitude', -74.4057):.4f}")
                
                # Status selection
                status = st.selectbox(
                    "Status",
                    ["Pending", "In Progress", "Completed"],
                    key=f"status_{idx}",
                    index=["Pending", "In Progress", "Completed"].index(location.get('status', 'Pending'))
                )
                location['status'] = status
                
                # Checklist
                st.markdown("#### Checklist")
                if location['address'] not in st.session_state.project_checklists[project_key]:
                    st.session_state.project_checklists[project_key][location['address']] = {
                        'Site Preparation': False,
                        'Materials Delivered': False,
                        'Work Started': False,
                        'Work Completed': False,
                        'Final Inspection': False,
                        'Client Approval': False
                    }
                
                checklist = st.session_state.project_checklists[project_key][location['address']]
                for item in checklist:
                    checklist[item] = st.checkbox(
                        item,
                        value=checklist[item],
                        key=f"check_{idx}_{item}"
                    )
                
                # Notes section
                if 'notes' not in location:
                    location['notes'] = ""
                location['notes'] = st.text_area(
                    "Notes",
                    value=location['notes'],
                    key=f"notes_{idx}"
                )
                
                # Delete location button
                if st.button("Delete Location", key=f"delete_{idx}"):
                    st.session_state.project_locations[project_key].pop(idx)
                    st.rerun()
        
        # Project progress
        st.markdown("### Project Progress")
        if st.session_state.project_locations[project_key]:
            total_locations = len(st.session_state.project_locations[project_key])
            completed = sum(1 for loc in st.session_state.project_locations[project_key] 
                          if loc['status'] == 'Completed')
            in_progress = sum(1 for loc in st.session_state.project_locations[project_key] 
                            if loc['status'] == 'In Progress')
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Locations", total_locations)
            with col2:
                st.metric("In Progress", in_progress)
            with col3:
                st.metric("Completed", completed)
            
            # Progress bar
            progress = completed / total_locations
            st.progress(progress)
            st.markdown(f"**Overall Progress:** {progress * 100:.1f}%")

def format_sheet_name(name):
    """Format string to be valid sheet name"""
    # Remove invalid characters
    invalid_chars = '[]:*?/\\'
    for char in invalid_chars:
        name = str(name).replace(char, '')
    # Truncate to 31 characters (Google Sheets limit)
    return name[:31]

def get_recent_bids(worksheet, project_name=None):
    """Get recent bids from Google Sheet"""
    try:
        data = worksheet.get_all_records()
        if not data:
            return []
        
        df = pd.DataFrame(data)
        if project_name:
            df = df[df['Project Name'] == project_name]
        
        # Save contractors and projects to session state
        st.session_state.saved_contractors.update(df['Contractor'].unique())
        for _, row in df.iterrows():
            project_name = format_sheet_name(str(row['Project Name']))
            if project_name not in st.session_state.saved_projects:
                st.session_state.saved_projects[project_name] = {
                    'owner': row['Project Owner'],
                    'location': row['Location'],
                    'status': 'Not Started',
                    'start_date': row['Date'],
                    'last_updated': datetime.now().strftime('%Y-%m-%d')
                }
        
        return df.to_dict('records')[-5:]
    except Exception as e:
        st.error(f"Error loading bid history: {str(e)}")
        return []

def main():
    st.title("📊 Bid Tracker")
    
    # Initialize Google services and get spreadsheet
    drive_service, sheets_client, spreadsheet = get_google_services()
    if not drive_service or not sheets_client:
        st.error("Failed to initialize Google services. Please check your credentials.")
        return
        
    # Don't proceed if no spreadsheet is connected
    if not spreadsheet:
        st.error("Could not connect to the bid tracking spreadsheet.")
        return
    
    # Add navigation
    page = st.sidebar.radio("Navigation", ["Bid Entry", "Project Tracking", "Project Status"])
    
    if page == "Bid Entry":
        st.markdown("### New Bid")
        
        # Get materials list and stats
        materials_data = get_materials_from_sheet(spreadsheet)
        material_list = [m['Material'] for m in materials_data if m['Material'].strip()]
        material_stats = get_material_stats(spreadsheet)
        
        # Add "New Project" option to project selection
        projects = db.get_projects()
        project_names = [p[0] for p in projects]
        project_choice = st.selectbox(
            "Select Project",
            options=["Create New Project"] + project_names
        )
        
        if project_choice == "Create New Project":
            st.markdown("### Create New Project")
            col1, col2 = st.columns(2)
            
            with col1:
                new_project_name = st.text_input("Project Name")
            with col2:
                new_project_owner = st.text_input("Project Owner")
                
            if st.button("Create Project"):
                if new_project_name and new_project_owner:
                    if create_new_project(spreadsheet, new_project_name, new_project_owner):
                        st.rerun()
                else:
                    st.error("Please enter both project name and owner")
            
            st.markdown("---")
        
        selected_project = project_choice if project_choice != "Create New Project" else None
        
        if selected_project:
            # Get project owner
            project_owner = db.get_project_owner(selected_project)
            st.info(f"Project Owner: {project_owner}")
            
            # Display bid history for the selected project
            try:
                display_bid_history(spreadsheet, selected_project)
            except Exception as e:
                st.error(f"Error displaying bid history: {str(e)}")
            
            # Rest of bid entry form...
            # ... (keep existing code) ...
    
    elif page == "Project Tracking":
        project_tracking_dashboard(spreadsheet)
    elif page == "Project Status":
        project_status_dashboard(spreadsheet)

if __name__ == "__main__":
    main()
