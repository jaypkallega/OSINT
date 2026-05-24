"""
Neo4j graph database integration for relationship mapping.
Visualize connections between emails, usernames, domains, and breaches.
"""
from typing import Dict, Any, List, Optional
from neo4j import GraphDatabase
from config import settings


class Neo4jGraph:
    """Manage Neo4j graph database for OSINT relationship mapping"""
    
    def __init__(self):
        self.uri = settings.NEO4J_URI
        self.user = settings.NEO4J_USER
        self.password = settings.NEO4J_PASSWORD
        self.driver = None
    
    def connect(self) -> bool:
        """Establish connection to Neo4j"""
        try:
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password)
            )
            # Test connection
            self.driver.verify_connectivity()
            return True
        except Exception as e:
            print(f"Neo4j connection failed: {e}")
            return False
    
    def disconnect(self):
        """Close Neo4j connection"""
        if self.driver:
            self.driver.close()
    
    def add_email_node(self, email: str) -> Dict[str, Any]:
        """Add or merge an email node"""
        query = """
        MERGE (e:Email {address: $email})
        ON CREATE SET e.created_at = datetime()
        ON MATCH SET e.updated_at = datetime()
        RETURN e
        """
        
        with self.driver.session() as session:
            result = session.run(query, email=email)
            record = result.single()
            return record["e"] if record else None
    
    def add_username_node(self, username: str) -> Dict[str, Any]:
        """Add or merge a username node"""
        query = """
        MERGE (u:Username {name: $username})
        ON CREATE SET u.created_at = datetime()
        ON MATCH SET u.updated_at = datetime()
        RETURN u
        """
        
        with self.driver.session() as session:
            result = session.run(query, username=username)
            record = result.single()
            return record["u"] if record else None
    
    def add_breach_node(self, breach_name: str, properties: Optional[Dict] = None) -> Dict[str, Any]:
        """Add or merge a breach node"""
        query = """
        MERGE (b:Breach {name: $breach_name})
        ON CREATE SET b += $properties, b.created_at = datetime()
        ON MATCH SET b += $properties, b.updated_at = datetime()
        RETURN b
        """
        
        props = properties or {}
        props["name"] = breach_name
        
        with self.driver.session() as session:
            result = session.run(query, breach_name=breach_name, properties=props)
            record = result.single()
            return record["b"] if record else None
    
    def add_platform_node(self, platform: str) -> Dict[str, Any]:
        """Add or merge a social platform node"""
        query = """
        MERGE (p:Platform {name: $platform})
        ON CREATE SET p.created_at = datetime()
        RETURN p
        """
        
        with self.driver.session() as session:
            result = session.run(query, platform=platform)
            record = result.single()
            return record["p"] if record else None
    
    def link_email_username(self, email: str, username: str) -> Dict[str, Any]:
        """Create relationship between email and username"""
        query = """
        MATCH (e:Email {address: $email})
        MATCH (u:Username {name: $username})
        MERGE (e)-[:ASSOCIATED_WITH]->(u)
        ON CREATE SET rel.created_at = datetime()
        RETURN e, u, rel
        """
        
        with self.driver.session() as session:
            result = session.run(query, email=email, username=username)
            record = result.single()
            return dict(record) if record else None
    
    def link_email_breach(self, email: str, breach_name: str) -> Dict[str, Any]:
        """Create relationship between email and breach"""
        query = """
        MATCH (e:Email {address: $email})
        MATCH (b:Breach {name: $breach_name})
        MERGE (e)-[:COMPROMISED_IN]->(b)
        ON CREATE SET rel.discovered_at = datetime()
        RETURN e, b, rel
        """
        
        with self.driver.session() as session:
            result = session.run(query, email=email, breach_name=breach_name)
            record = result.single()
            return dict(record) if record else None
    
    def link_username_platform(self, username: str, platform: str, url: Optional[str] = None) -> Dict[str, Any]:
        """Create relationship between username and platform"""
        query = """
        MATCH (u:Username {name: $username})
        MATCH (p:Platform {name: $platform})
        MERGE (u)-[:HAS_ACCOUNT {url: $url}]->(p)
        ON CREATE SET rel.created_at = datetime()
        RETURN u, p, rel
        """
        
        with self.driver.session() as session:
            result = session.run(query, username=username, platform=platform, url=url)
            record = result.single()
            return dict(record) if record else None
    
    def populate_from_scan_results(
        self,
        email: str,
        username: Optional[str] = None,
        breaches: Optional[List[Dict]] = None,
        social_accounts: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Populate graph from scan results.
        
        Creates nodes and relationships for:
        - Email
        - Username (if provided)
        - Breaches
        - Social media accounts
        """
        results = {
            "nodes_created": 0,
            "relationships_created": 0,
            "errors": []
        }
        
        try:
            # Add email node
            self.add_email_node(email)
            results["nodes_created"] += 1
            
            # Add username and link to email
            if username:
                self.add_username_node(username)
                self.link_email_username(email, username)
                results["nodes_created"] += 1
                results["relationships_created"] += 1
            
            # Add breaches and link to email
            if breaches:
                for breach in breaches:
                    breach_name = breach.get("Name") or breach.get("name", "Unknown")
                    self.add_breach_node(breach_name, breach)
                    self.link_email_breach(email, breach_name)
                    results["nodes_created"] += 1
                    results["relationships_created"] += 1
            
            # Add social accounts and link
            if social_accounts:
                for account in social_accounts:
                    platform = account.get("platform", "Unknown")
                    account_username = account.get("username", username)
                    url = account.get("url")
                    
                    if account_username:
                        self.add_username_node(account_username)
                        self.add_platform_node(platform)
                        self.link_username_platform(account_username, platform, url)
                        
                        # Link to primary email if different
                        if account_username != username:
                            self.link_email_username(email, account_username)
                        
                        results["nodes_created"] += 2
                        results["relationships_created"] += 2
            
            return results
            
        except Exception as e:
            results["errors"].append(str(e))
            return results
    
    def get_email_graph(self, email: str) -> Dict[str, Any]:
        """
        Get complete graph for an email address.
        
        Returns all connected nodes and relationships.
        """
        query = """
        MATCH (e:Email {address: $email})
        OPTIONAL MATCH (e)-[:ASSOCIATED_WITH]->(u:Username)
        OPTIONAL MATCH (e)-[:COMPROMISED_IN]->(b:Breach)
        OPTIONAL MATCH (u)-[:HAS_ACCOUNT]->(p:Platform)
        RETURN e, 
               collect(DISTINCT u) as usernames,
               collect(DISTINCT b) as breaches,
               collect(DISTINCT p) as platforms
        """
        
        with self.driver.session() as session:
            result = session.run(query, email=email)
            record = result.single()
            
            if not record:
                return None
            
            return {
                "email": dict(record["e"]),
                "usernames": [dict(u) for u in record["usernames"]],
                "breaches": [dict(b) for b in record["breaches"]],
                "platforms": [dict(p) for p in record["platforms"]]
            }
    
    def get_all_nodes(self, label: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all nodes, optionally filtered by label"""
        if label:
            query = f"MATCH (n:{label}) RETURN n"
        else:
            query = "MATCH (n) RETURN n"
        
        with self.driver.session() as session:
            result = session.run(query)
            return [dict(record["n"]) for record in result]
    
    def get_statistics(self) -> Dict[str, int]:
        """Get graph statistics"""
        query = """
        MATCH ()
        RETURN 
            count(DISTINCT CASE WHEN labels(_) CONTAINS 'Email' THEN _ END) as emails,
            count(DISTINCT CASE WHEN labels(_) CONTAINS 'Username' THEN _ END) as usernames,
            count(DISTINCT CASE WHEN labels(_) CONTAINS 'Breach' THEN _ END) as breaches,
            count(DISTINCT CASE WHEN labels(_) CONTAINS 'Platform' THEN _ END) as platforms,
            count(()) as total_nodes,
            count(--> ) as total_relationships
        """
        
        with self.driver.session() as session:
            result = session.run(query)
            record = result.single()
            
            if record:
                return {
                    "emails": record["emails"] or 0,
                    "usernames": record["usernames"] or 0,
                    "breaches": record["breaches"] or 0,
                    "platforms": record["platforms"] or 0,
                    "total_nodes": record["total_nodes"] or 0,
                    "total_relationships": record["total_relationships"] or 0
                }
        
        return {}
    
    def clear_graph(self):
        """Delete all nodes and relationships (use with caution!)"""
        query = """
        MATCH (n)
        DETACH DELETE n
        """
        
        with self.driver.session() as session:
            session.run(query)


# Singleton instance
_graph_instance = None

def get_graph() -> Neo4jGraph:
    """Get or create Neo4j graph instance"""
    global _graph_instance
    if _graph_instance is None:
        _graph_instance = Neo4jGraph()
        _graph_instance.connect()
    return _graph_instance
