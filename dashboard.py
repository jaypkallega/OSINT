"""
Streamlit dashboard for OSINT Privacy Intelligence App.
Provides user-friendly interface for all OSINT operations.
"""
import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import datetime
from typing import Dict, Any, List

# Configuration
BACKEND_URL = "http://127.0.0.1:8000"
st.set_page_config(
    page_title="OSINT Privacy Intelligence",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {font-size: 2.5rem; font-weight: bold; color: #1f77b4;}
    .metric-card {background-color: #f0f2f6; padding: 20px; border-radius: 10px;}
    .warning-box {background-color: #fff3cd; padding: 15px; border-radius: 5px; border-left: 4px solid #ffc107;}
    .danger-box {background-color: #f8d7da; padding: 15px; border-radius: 5px; border-left: 4px solid #dc3545;}
    .success-box {background-color: #d4edda; padding: 15px; border-radius: 5px; border-left: 4px solid #28a745;}
</style>
""", unsafe_allow_html=True)


def check_backend_health() -> bool:
    """Check if backend is running"""
    try:
        response = requests.get(f"{BACKEND_URL}/api/health", timeout=5)
        return response.status_code == 200
    except Exception:
        return False


def perform_scan(email: str, username: str = None, password: str = None) -> Dict[str, Any]:
    """Send scan request to backend"""
    payload = {
        "email": email,
        "username": username,
        "check_breaches": True,
        "check_social": True
    }
    
    if password:
        payload["password"] = password
    
    try:
        response = requests.post(f"{BACKEND_URL}/api/scan", json=payload, timeout=120)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Backend error: {str(e)}")
        return {}


def check_password(password: str) -> Dict[str, Any]:
    """Check password exposure"""
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/password/check",
            json={"password": password},
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e)}


def get_exposure_score(email: str) -> Dict[str, Any]:
    """Get exposure score for email"""
    try:
        response = requests.get(f"{BACKEND_URL}/api/exposure-score/{email}", timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return {}


# Main app
def main():
    # Header
    st.markdown('<p class="main-header">🔍 OSINT Privacy Intelligence</p>', unsafe_allow_html=True)
    st.markdown("### Personal Privacy Assessment & Monitoring Dashboard")
    st.markdown("---")
    
    # Check backend health
    if not check_backend_health():
        st.error("⚠️ Backend server is not running. Please start it with: `uvicorn main:app --host 127.0.0.1 --port 8000`")
        st.stop()
    
    # Sidebar
    with st.sidebar:
        st.header("Navigation")
        page = st.radio(
            "Go to:",
            ["🏠 Dashboard", "🔐 Breach Check", "🌐 Social Footprint", "📊 Exposure Score"],
            label_visibility="collapsed"
        )
        
        st.markdown("---")
        st.info("**Security Notice:**\n\nThis tool is for **personal use only**. Only scan your own data.")
        
        st.markdown("---")
        st.markdown("**Quick Stats**")
        stats_placeholder = st.empty()
    
    # Page routing
    if "Dashboard" in page:
        show_dashboard()
    elif "Breach" in page:
        show_breach_check()
    elif "Social" in page:
        show_social_footprint()
    elif "Exposure" in page:
        show_exposure_score()


def show_dashboard():
    """Main dashboard view"""
    st.header("🏠 Privacy Dashboard")
    
    # Quick scan form
    with st.expander("🚀 Quick Scan", expanded=True):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            email = st.text_input("Email Address", placeholder="your@email.com")
        
        with col2:
            username = st.text_input("Username (optional)", placeholder="johndoe")
        
        with col3:
            password = st.text_input("Password Check (optional)", type="password", placeholder="Test a password")
        
        if st.button("Start Scan", type="primary", use_container_width=True):
            if email:
                with st.spinner("Running comprehensive OSINT scan..."):
                    result = perform_scan(email, username or email.split('@')[0], password)
                    
                    if result:
                        st.session_state['last_scan'] = result
                        st.success("✅ Scan completed!")
                        
                        # Display results
                        display_scan_results(result)
                    else:
                        st.error("Scan failed. Is the backend running?")
            else:
                st.warning("Please enter at least an email address")
    
    # Recent scans
    if 'last_scan' in st.session_state:
        st.markdown("---")
        st.subheader("📋 Latest Scan Results")
        display_scan_results(st.session_state['last_scan'])


def display_scan_results(result: Dict[str, Any]):
    """Display comprehensive scan results"""
    # Top metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        score = result.get('exposure_score', 0)
        delta = "Higher risk" if score > 50 else "Lower risk"
        st.metric("Exposure Score", f"{score:.0f}/100", delta=delta)
    
    with col2:
        breaches = len([b for b in result.get('breaches', []) if 'error' not in b and 'warning' not in b])
        st.metric("Data Breaches", breaches)
    
    with col3:
        accounts = len([a for a in result.get('social_accounts', []) if 'error' not in a])
        st.metric("Social Accounts", accounts)
    
    with col4:
        password_status = result.get('password_exposed', {})
        if password_status.get('found'):
            st.metric("Password Status", "⚠️ EXPOSED", delta="Critical")
        else:
            st.metric("Password Status", "✅ Safe")
    
    # Detailed sections
    st.markdown("---")
    
    # Breaches
    if result.get('breaches'):
        with st.expander(f"🚨 Data Breaches ({len(result['breaches'])})"):
            for breach in result['breaches']:
                if 'error' in breach:
                    st.warning(f"Error: {breach['error']}")
                elif 'warning' in breach:
                    st.info(breach['warning'])
                else:
                    st.markdown(f"**{breach.get('Name', 'Unknown')}**")
                    st.write(f"*Date:* {breach.get('BreachDate', 'Unknown')}")
                    st.write(f"*Description:* {breach.get('Description', 'No description')}")
                    if breach.get('DataClasses'):
                        st.write(f"*Compromised data:* {', '.join(breach['DataClasses'])}")
                    st.markdown("---")
    
    # Social accounts
    if result.get('social_accounts'):
        with st.expander(f"🌐 Social Media Accounts ({len(result['social_accounts'])})"):
            df = pd.DataFrame(result['social_accounts'])
            if not df.empty:
                st.dataframe(df[['platform', 'username', 'url', 'source_tool']], use_container_width=True)
    
    # Password exposure
    if result.get('password_exposed'):
        with st.expander("🔐 Password Exposure Check"):
            pwd_result = result['password_exposed']
            if 'error' in pwd_result:
                st.error(pwd_result['error'])
            elif pwd_result.get('found'):
                st.error(f"❌ This password was found in **{pwd_result['count']:,}** breaches!")
                st.warning("Change this password immediately on all accounts where you use it.")
            else:
                st.success("✅ Good news! This password wasn't found in known breaches.")
                st.info("However, always use unique passwords for each account.")


def show_breach_check():
    """Dedicated breach check page"""
    st.header("🔐 Breach Analysis")
    st.markdown("Check if your email has been compromised in data breaches")
    
    email = st.text_input("Enter email address", key="breach_email")
    
    if st.button("Check Breaches", type="primary"):
        if email:
            with st.spinner("Checking Have I Been Pwned database..."):
                result = perform_scan(email=email)
                
                if result and result.get('breaches'):
                    breach_count = len([b for b in result['breaches'] if 'error' not in b])
                    
                    if breach_count > 0:
                        st.error(f"⚠️ Found in **{breach_count}** data breaches!")
                        
                        for breach in result['breaches']:
                            if 'Name' in breach:
                                with st.container():
                                    st.markdown(f"### {breach['Name']}")
                                    col1, col2 = st.columns([3, 1])
                                    with col1:
                                        st.write(breach.get('Description', ''))
                                        st.write(f"**Compromised:** {breach.get('BreachDate', 'Unknown')}")
                                        if breach.get('DataClasses'):
                                            st.write(f"**Data types:** {', '.join(breach['DataClasses'])}")
                                    with col2:
                                        st.metric("Accounts", f"{breach.get('PwnCount', 'N/A'):,}")
                                    st.markdown("---")
                    else:
                        st.success("✅ No breaches found for this email!")
                else:
                    st.info("ℹ️ No HIBP API key configured. Breach check unavailable.")
        else:
            st.warning("Please enter an email address")


def show_social_footprint():
    """Social footprint discovery page"""
    st.header("🌐 Social Footprint Discovery")
    st.markdown("Find social media accounts associated with a username")
    
    col1, col2 = st.columns(2)
    with col1:
        username = st.text_input("Username", placeholder="johndoe")
    with col2:
        email = st.text_input("Associated Email (optional)", placeholder="user@example.com")
    
    if st.button("Discover Accounts", type="primary"):
        if username:
            with st.spinner("Scanning multiple platforms... This may take a minute."):
                result = perform_scan(email=email or f"{username}@test.com", username=username)
                
                if result and result.get('social_accounts'):
                    accounts = [a for a in result['social_accounts'] if 'error' not in a]
                    
                    if accounts:
                        st.success(f"Found **{len(accounts)}** social media accounts!")
                        
                        # Create dataframe
                        df = pd.DataFrame(accounts)
                        
                        # Group by platform
                        platform_counts = df['platform'].value_counts()
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.subheader("By Platform")
                            st.bar_chart(platform_counts)
                        
                        with col2:
                            st.subheader("By Tool")
                            tool_counts = df['source_tool'].value_counts()
                            st.bar_chart(tool_counts)
                        
                        st.subheader("All Discovered Accounts")
                        st.dataframe(df, use_container_width=True)
                    else:
                        st.info("No social accounts found for this username")
                else:
                    st.info("No results. Make sure Sherlock/Holehe/Maigret are installed.")
        else:
            st.warning("Please enter a username")


def show_exposure_score():
    """Exposure score analysis page"""
    st.header("📊 Privacy Exposure Score")
    st.markdown("Understand your privacy risk level")
    
    email = st.text_input("Enter email to check score", key="score_email")
    
    if email:
        score_data = get_exposure_score(email)
        
        if score_data and 'error' not in score_data:
            score = score_data.get('score', 0)
            
            # Gauge chart
            fig = px.scatter(
                x=[score],
                y=[0],
                size=[score * 3],
                color=[score],
                color_continuous_scale=['green', 'yellow', 'red'],
                range_color=[0, 100],
                size_max=100
            )
            fig.update_layout(
                xaxis=dict(range=[0, 110], showticklabels=False),
                yaxis=dict(range=[-1, 1], showticklabels=False),
                height=300,
                showlegend=False
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Score interpretation
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Overall Score", f"{score:.0f}/100")
            
            with col2:
                st.metric("Breaches Found", score_data.get('breach_count', 0))
            
            with col3:
                st.metric("Social Accounts", score_data.get('social_account_count', 0))
            
            # Risk level
            if score < 30:
                st.success("🟢 **Low Risk** - Your digital footprint is relatively small")
            elif score < 60:
                st.warning("🟡 **Medium Risk** - Consider reviewing your privacy settings")
            else:
                st.error("🔴 **High Risk** - Take action to reduce your exposure")
            
            # Recommendations
            st.markdown("### 📋 Recommendations")
            
            if score_data.get('breach_count', 0) > 0:
                st.write("- ✅ Change passwords for breached accounts")
                st.write("- ✅ Enable two-factor authentication")
                st.write("- ✅ Use a password manager")
            
            if score_data.get('social_account_count', 0) > 10:
                st.write("- ✅ Review and delete unused social media accounts")
                st.write("- ✅ Adjust privacy settings on active accounts")
            
            if score_data.get('password_compromised'):
                st.write("- 🔴 **URGENT:** Change compromised password immediately")
                st.write("- Never reuse passwords across multiple sites")
        else:
            st.info("No score data available yet. Run a scan first.")


if __name__ == "__main__":
    main()
