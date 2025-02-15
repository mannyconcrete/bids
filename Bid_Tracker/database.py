import sqlite3
import json
from datetime import datetime

class Database:
    def __init__(self):
        """Initialize the database"""
        try:
            self.conn = sqlite3.connect('bid_tracker.db', check_same_thread=False)
            self.cursor = self.conn.cursor()
            
            # Create tables if they don't exist
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS project_locations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_name TEXT,
                    address TEXT,
                    status TEXT DEFAULT 'Not Started',
                    coordinates TEXT,
                    notes TEXT,
                    checklist TEXT,
                    date_added TEXT,
                    UNIQUE(project_name, address)
                )
            """)
            self.conn.commit()
            
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
            # Check if location already exists
            if self.location_exists(project_name, location_data['address']):
                print(f"Location {location_data['address']} already exists for project {project_name}")
                return False

            # Validate project exists
            self.cursor.execute("SELECT id FROM projects WHERE name = ?", (project_name,))
            if not self.cursor.fetchone():
                print(f"Project {project_name} does not exist")
                return False

            # Print debug info
            print(f"Adding location: {location_data}")
            
            # Ensure all required fields exist
            location_data.setdefault('status', 'Not Started')
            location_data.setdefault('notes', '')
            location_data.setdefault('checklist', {})
            location_data.setdefault('date_added', datetime.now().strftime("%Y-%m-%d"))

            # Insert location
            self.cursor.execute("""
                INSERT OR REPLACE INTO project_locations 
                (project_name, address, status, coordinates, notes, checklist, date_added)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                project_name,
                location_data['address'],
                location_data['status'],
                json.dumps(location_data['coordinates']),
                location_data['notes'],
                json.dumps(location_data['checklist']),
                location_data['date_added']
            ))
            self.conn.commit()
            print(f"Successfully added location to database")
            return True
        except Exception as e:
            print(f"Detailed error adding project location: {str(e)}")
            print(f"Project name: {project_name}")
            print(f"Location data: {location_data}")
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
