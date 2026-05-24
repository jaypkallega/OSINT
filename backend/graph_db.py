"""
Neo4j Graph Database Module for OPIP.
Handles relationship mapping between entities: Email, Username, Breach, Social Account, Phone, Domain.
"""
import os
from typing import Optional, List, Dict, Any

try:
    from neo4j import GraphDatabase
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    print("⚠️ Neo4j driver not installed. Graph features disabled.")

# Configuration
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
NEO4J_ENABLED = os.getenv("NEO4J_ENABLED", "false").lower() == "true"

class Neo4jManager:
    def __init__(self):
        self.driver = None
        self.enabled = NEO4J_ENABLED and NEO4J_AVAILABLE
        
    def connect(self):
        """Establish connection to Neo4j."""
        if not self.enabled:
            print("ℹ️ Neo4j is disabled or unavailable.")
            return False
        
        try:
            self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
            # Test connection
            with self.driver.session() as session:
                session.run("MATCH (n) RETURN count(n) LIMIT 1")
            print(f"✅ Connected to Neo4j at {NEO4J_URI}")
            return True
        except Exception as e:
            print(f"❌ Neo4j connection failed: {str(e)}")
            self.enabled = False
            return False
    
    def close(self):
        """Close Neo4j connection."""
        if self.driver:
            self.driver.close()
            print("Neo4j connection closed.")
    
    def create_email_node(self, email: str):
        """Create or match an Email node."""
        if not self.enabled or not self.driver:
            return
        
        query = """
        MERGE (e:Email {address: $email})
        RETURN e
        """
        with self.driver.session() as session:
            session.run(query, email=email)
    
    def create_username_node(self, username: str):
        """Create or match a Username node."""
        if not self.enabled or not self.driver:
            return
        
        query = """
        MERGE (u:Username {value: $username})
        RETURN u
        """
        with self.driver.session() as session:
            session.run(query, username=username)
    
    def create_breach_node(self, breach_name: str, breach_date: str = None, description: str = None):
        """Create or match a Breach node."""
        if not self.enabled or not self.driver:
            return
        
        query = """
        MERGE (b:Breach {name: $breach_name})
        SET b.breach_date = $breach_date,
            b.description = $description
        RETURN b
        """
        with self.driver.session() as session:
            session.run(query, breach_name=breach_name, breach_date=breach_date, description=description)
    
    def create_social_account_node(self, platform: str, username: str, url: str = None):
        """Create or match a SocialAccount node."""
        if not self.enabled or not self.driver:
            return
        
        query = """
        MERGE (s:SocialAccount {platform: $platform, username: $username})
        SET s.url = $url
        RETURN s
        """
        with self.driver.session() as session:
            session.run(query, platform=platform, username=username, url=url)
    
    def create_phone_node(self, phone_number: str, carrier: str = None, country: str = None):
        """Create or match a Phone node."""
        if not self.enabled or not self.driver:
            return
        
        query = """
        MERGE (p:Phone {number: $phone_number})
        SET p.carrier = $carrier,
            p.country = $country
        RETURN p
        """
        with self.driver.session() as session:
            session.run(query, phone_number=phone_number, carrier=carrier, country=country)
    
    def link_email_to_breach(self, email: str, breach_name: str):
        """Create FOUND_IN relationship between Email and Breach."""
        if not self.enabled or not self.driver:
            return
        
        query = """
        MATCH (e:Email {address: $email})
        MATCH (b:Breach {name: $breach_name})
        MERGE (e)-[:FOUND_IN]->(b)
        """
        with self.driver.session() as session:
            session.run(query, email=email, breach_name=breach_name)
    
    def link_email_to_username(self, email: str, username: str):
        """Create ASSOCIATED_WITH relationship between Email and Username."""
        if not self.enabled or not self.driver:
            return
        
        query = """
        MATCH (e:Email {address: $email})
        MATCH (u:Username {value: $username})
        MERGE (e)-[:ASSOCIATED_WITH]->(u)
        """
        with self.driver.session() as session:
            session.run(query, email=email, username=username)
    
    def link_username_to_social(self, username: str, platform: str, social_username: str):
        """Create REGISTERED_ON relationship between Username and SocialAccount."""
        if not self.enabled or not self.driver:
            return
        
        query = """
        MATCH (u:Username {value: $username})
        MATCH (s:SocialAccount {platform: $platform, username: $social_username})
        MERGE (u)-[:REGISTERED_ON]->(s)
        """
        with self.driver.session() as session:
            session.run(query, username=username, platform=platform, social_username=social_username)
    
    def link_email_to_phone(self, email: str, phone_number: str):
        """Create ASSOCIATED_WITH relationship between Email and Phone."""
        if not self.enabled or not self.driver:
            return
        
        query = """
        MATCH (e:Email {address: $email})
        MATCH (p:Phone {number: $phone_number})
        MERGE (e)-[:ASSOCIATED_WITH]->(p)
        """
        with self.driver.session() as session:
            session.run(query, email=email, phone_number=phone_number)
    
    def build_graph_from_scan(self, email: str, username: str, breaches: List[Dict], social_accounts: List[Dict]):
        """Build complete graph from scan results."""
        if not self.enabled or not self.driver:
            print("ℹ️ Skipping graph build - Neo4j not enabled.")
            return
        
        print("🕸️ Building Neo4j graph...")
        
        # Create central nodes
        self.create_email_node(email)
        if username:
            self.create_username_node(username)
            self.link_email_to_username(email, username)
        
        # Add breaches
        for breach in breaches:
            if 'error' in breach or 'warning' in breach:
                continue
            breach_name = breach.get('Name', 'Unknown')
            self.create_breach_node(
                breach_name,
                breach.get('BreachDate'),
                breach.get('Description')
            )
            self.link_email_to_breach(email, breach_name)
        
        # Add social accounts
        for account in social_accounts:
            if 'error' in account or 'warning' in account:
                continue
            platform = account.get('platform', 'Unknown')
            social_username = account.get('username', '')
            url = account.get('url', '')
            
            self.create_social_account_node(platform, social_username, url)
            
            # Link through username if available
            if username:
                self.link_username_to_social(username, platform, social_username)
        
        print("✅ Graph built successfully.")
    
    def get_entity_relationships(self, email: str) -> List[Dict[str, Any]]:
        """Get all relationships for an email entity."""
        if not self.enabled or not self.driver:
            return []
        
        query = """
        MATCH (e:Email {address: $email})-[r]-(connected)
        RETURN e, r, connected
        """
        
        relationships = []
        with self.driver.session() as session:
            result = session.run(query, email=email)
            for record in result:
                relationships.append({
                    'source': record['e']['address'],
                    'relationship': record['r'].type,
                    'target': dict(record['connected'])
                })
        
        return relationships
    
    def export_graph_to_json(self, email: str) -> Dict[str, Any]:
        """Export graph data for visualization."""
        if not self.enabled or not self.driver:
            return {'nodes': [], 'links': []}
        
        query = """
        MATCH (e:Email {address: $email})-[r]-(connected)
        RETURN e, r, connected
        UNION
        MATCH (e:Email {address: $email})<-[]-(connected)-[r2]-(further)
        RETURN connected as e, r2 as r, further as connected
        """
        
        nodes = {}
        links = []
        
        with self.driver.session() as session:
            result = session.run(query, email=email)
            for record in result:
                source_data = dict(record['e'])
                target_data = dict(record['connected'])
                rel_type = record['r'].type
                
                # Add nodes
                source_id = f"{list(source_data.keys())[0]}:{list(source_data.values())[0]}"
                target_id = f"{list(target_data.keys())[0]}:{list(target_data.values())[0]}"
                
                if source_id not in nodes:
                    nodes[source_id] = {
                        'id': source_id,
                        'label': list(source_data.values())[0],
                        'type': list(source_data.keys())[0]
                    }
                
                if target_id not in nodes:
                    nodes[target_id] = {
                        'id': target_id,
                        'label': list(target_data.values())[0],
                        'type': list(target_data.keys())[0]
                    }
                
                links.append({
                    'source': source_id,
                    'target': target_id,
                    'relationship': rel_type
                })
        
        return {
            'nodes': list(nodes.values()),
            'links': links
        }

# Global instance
neo4j_manager = Neo4jManager()

def init_neo4j():
    """Initialize Neo4j connection."""
    return neo4j_manager.connect()

def close_neo4j():
    """Close Neo4j connection."""
    neo4j_manager.close()
