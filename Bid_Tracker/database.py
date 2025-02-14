import sqlite3
from datetime import datetime

class Database:
    def __init__(self):
        self.conn = sqlite3.connect('bid_tracker.db', check_same_thread=False)
        self.create_tables()
    
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
