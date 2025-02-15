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
                    status TEXT,
                    coordinates TEXT,
                    notes TEXT,
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
        # Get locations for a project
        pass

    def add_project_location(self, project_name, location_data):
        # Add a new location to a project
        pass

    def update_project_location_status(self, project_name, location_address, new_status):
        # Update location status
        pass

    def update_project_location_notes(self, project_name, location_address, new_notes):
        # Update location notes
        pass

    def delete_project_location(self, project_name, location_address):
        # Delete a location
        pass
