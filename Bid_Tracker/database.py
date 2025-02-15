import sqlite3
import json
from datetime import datetime

class Database:
    def __init__(self):
        """Initialize the database"""
        try:
            self.conn = sqlite3.connect('bid_tracker.db', check_same_thread=False)
            self.cursor = self.conn.cursor()
            
            # Drop and recreate the project_locations table
            self.cursor.execute("DROP TABLE IF EXISTS project_locations")
            
            # Create table with all required columns
            self.cursor.execute("""
                CREATE TABLE project_locations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_name TEXT NOT NULL,
                    address TEXT NOT NULL,
                    status TEXT DEFAULT 'Not Started',
                    coordinates TEXT,
                    notes TEXT DEFAULT '',
                    checklist TEXT DEFAULT '{}',
                    date_added TEXT,
                    UNIQUE(project_name, address),
                    FOREIGN KEY(project_name) REFERENCES projects(name)
                )
            """)
            self.conn.commit()
            
            # Verify table structure
            self.cursor.execute("PRAGMA table_info(project_locations)")
            columns = self.cursor.fetchall()
            print("DEBUG: Table columns:", [col[1] for col in columns])
            
        except Exception as e:
            print(f"Database initialization error: {str(e)}")
    
    def create_tables(self):
        cursor = self.conn.cursor()
        
        # Create Projects table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                owner TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create Contractors table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS contractors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                location TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create Materials table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.conn.commit()
    
    def add_project(self, name, owner):
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                'INSERT INTO projects (name, owner) VALUES (?, ?)',
                (name, owner)
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
    
    def get_projects(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT name, owner FROM projects ORDER BY name')
        return cursor.fetchall()
    
    def add_contractor(self, name, location):
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                'INSERT INTO contractors (name, location) VALUES (?, ?)',
                (name, location)
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
    
    def get_contractors(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT name, location FROM contractors ORDER BY name')
        return cursor.fetchall()
    
    def add_material(self, name):
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                'INSERT INTO materials (name) VALUES (?)',
                (name,)
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
    
    def get_materials(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT name FROM materials ORDER BY name')
        return [row[0] for row in cursor.fetchall()]
    
    def get_contractor_location(self, name):
        cursor = self.conn.cursor()
        cursor.execute('SELECT location FROM contractors WHERE name = ?', (name,))
        result = cursor.fetchone()
        return result[0] if result else None
    
    def get_project_owner(self, project_name):
        """Get the owner of a specific project"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT owner FROM projects WHERE name = ?', (project_name,))
        result = cursor.fetchone()
        return result[0] if result else None

    def get_project_locations(self, project_name):
        """Get all locations for a project"""
        try:
            self.cursor.execute("""
                SELECT address, status, coordinates, notes, checklist, date_added 
                FROM project_locations 
                WHERE project_name = ?
            """, (project_name,))
            locations = self.cursor.fetchall()
            
            # Convert to list of dictionaries
            return [{
                'address': loc[0],
                'status': loc[1] or 'Not Started',  # Ensure status is never None
                'coordinates': json.loads(loc[2]) if loc[2] else None,
                'notes': loc[3] or '',
                'checklist': json.loads(loc[4]) if loc[4] else {},
                'date_added': loc[5]
            } for loc in locations]
        except Exception as e:
            print(f"Error getting project locations: {str(e)}")
            return []

    def location_exists(self, project_name, address):
        """Check if a location already exists for a project"""
        try:
            self.cursor.execute("""
                SELECT COUNT(*) FROM project_locations 
                WHERE project_name = ? AND address = ?
            """, (project_name, address))
            count = self.cursor.fetchone()[0]
            return count > 0
        except Exception as e:
            print(f"Error checking location existence: {str(e)}")
            return False

    def add_project_location(self, project_name, location_data):
        """Add a new location to a project"""
        try:
            # Verify table structure
            self.cursor.execute("PRAGMA table_info(project_locations)")
            columns = [col[1] for col in self.cursor.fetchall()]
            print(f"DEBUG: Available columns: {columns}")
            
            if 'checklist' not in columns:
                print("ERROR: Checklist column missing from table")
                return False

            # Print incoming data for debugging
            print("\nDEBUG: Starting add_project_location")
            print(f"Project name: {project_name}")
            print(f"Location data: {location_data}")

            # Validate project exists
            self.cursor.execute("SELECT name FROM projects WHERE name = ?", (project_name,))
            project = self.cursor.fetchone()
            if not project:
                print(f"ERROR: Project {project_name} does not exist in database")
                return False
            print(f"DEBUG: Project found: {project[0]}")

            # Ensure all required fields exist and are properly formatted
            try:
                formatted_data = {
                    'address': str(location_data['address']),
                    'status': str(location_data.get('status', 'Not Started')),
                    'coordinates': json.dumps(location_data['coordinates']),
                    'notes': str(location_data.get('notes', '')),
                    'checklist': json.dumps(location_data.get('checklist', {})),
                    'date_added': str(location_data.get('date_added', datetime.now().strftime("%Y-%m-%d")))
                }
                print("DEBUG: Data formatted successfully")
            except Exception as e:
                print(f"ERROR: Failed to format data: {str(e)}")
                return False

            # Print SQL query for debugging
            query = """
                INSERT INTO project_locations 
                (project_name, address, status, coordinates, notes, checklist, date_added)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """
            params = (
                project_name,
                formatted_data['address'],
                formatted_data['status'],
                formatted_data['coordinates'],
                formatted_data['notes'],
                formatted_data['checklist'],
                formatted_data['date_added']
            )
            print(f"DEBUG: Query: {query}")
            print(f"DEBUG: Parameters: {params}")

            # Execute the insert
            self.cursor.execute(query, params)
            self.conn.commit()
            print("DEBUG: Location added successfully")
            return True

        except sqlite3.IntegrityError as e:
            print(f"ERROR: Database integrity error: {str(e)}")
            if "UNIQUE constraint failed" in str(e):
                print("ERROR: This location already exists for this project")
            return False
        except Exception as e:
            print(f"ERROR: Unexpected error: {str(e)}")
            print(f"ERROR: Error type: {type(e)}")
            return False

    def update_project_location_status(self, project_name, location_address, new_status):
        """Update the status of a location"""
        try:
            self.cursor.execute("""
                UPDATE project_locations 
                SET status = ? 
                WHERE project_name = ? AND address = ?
            """, (new_status, project_name, location_address))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error updating location status: {str(e)}")
            return False

    def update_project_location_notes(self, project_name, location_address, new_notes):
        """Update the notes for a location"""
        try:
            self.cursor.execute("""
                UPDATE project_locations 
                SET notes = ? 
                WHERE project_name = ? AND address = ?
            """, (new_notes, project_name, location_address))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error updating location notes: {str(e)}")
            return False

    def delete_project_location(self, project_name, location_address):
        """Delete a location from a project"""
        try:
            self.cursor.execute("""
                DELETE FROM project_locations 
                WHERE project_name = ? AND address = ?
            """, (project_name, location_address))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error deleting location: {str(e)}")
            return False
