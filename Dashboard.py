import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import sys
import os

# Path ayarı
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utils.pocketbase_client import get_all_data
from utils.data_processor import (
    clean_dataframe, convert_date_columns, calculate_metrics,
    filter_columns_for_display, get_column_display_names,
    format_money_columns, apply_date_filter
)


# =================== SIMPLE AUTH SYSTEM ===================

def check_authentication():
    """Basit password authentication - Deploy-friendly"""

    # Master password'u environment'tan al
    MASTER_PASSWORD = st.secrets.get("DASHBOARD_PASSWORD", os.getenv("DASHBOARD_PASSWORD", "admin123"))

    # Session'da auth durumu
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False

    return st.session_state.authenticated, MASTER_PASSWORD


def show_login_page():
    """Login sayfası - Streamlit deploy için optimize"""

    st.set_page_config(
        page_title="🔐 Dashboard Login",
        page_icon="🔒",
        layout="centered"
    )

    # Centered login form
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.markdown("""
        <div style='text-align: center; padding: 2rem 0;'>
            <h1>🔐 Business Dashboard</h1>
            <p style='color: #666;'>Enter password to access analytics</p>
        </div>
        """, unsafe_allow_html=True)

        # Login form
        with st.form("login_form", clear_on_submit=True):
            password = st.text_input(
                "Password:",
                type="password",
                placeholder="Enter dashboard password"
            )

            col_a, col_b, col_c = st.columns([1, 2, 1])
            with col_b:
                login_clicked = st.form_submit_button(
                    "🚀 Access Dashboard",
                    use_container_width=True,
                    type="primary"
                )

            if login_clicked:
                _, master_password = check_authentication()

                if password == master_password:
                    st.session_state.authenticated = True
                    st.session_state.login_time = datetime.now()
                    st.success("✅ Login successful! Redirecting...")
                    st.rerun()
                else:
                    st.error("❌ Invalid password")

        # Info section
        st.markdown("---")
        st.markdown("""
        <div style='text-align: center; color: #888; font-size: 0.8em;'>
            <p>🔒 Secure access to business analytics dashboard</p>
            <p>💼 eBay & Amazon order tracking with profit analysis</p>
        </div>
        """, unsafe_allow_html=True)


def show_logout_option():
    """Logout butonu - Sidebar'da göster"""

    if st.session_state.get('authenticated', False):
        with st.sidebar:
            st.markdown("---")

            # Login info
            login_time = st.session_state.get('login_time')
            if login_time:
                time_str = login_time.strftime('%H:%M')
                st.caption(f"🔐 Logged in at {time_str}")

            # Logout button
            if st.button("🚪 Logout", type="secondary", use_container_width=True):
                # Clear auth session
                st.session_state.authenticated = False
                if 'login_time' in st.session_state:
                    del st.session_state.login_time

                # Clear all cache
                st.cache_data.clear()

                st.success("✅ Logged out successfully")
                st.rerun()


# =================== SESSION STATE MONTHLY EXPENSES ===================

# Session state'i initialize et
if 'monthly_expenses' not in st.session_state:
    st.session_state.monthly_expenses = {}


# Expense management fonksiyonları
def add_expense_to_month(month_key, name, amount):
    """Belirli aya gider ekle"""
    if month_key not in st.session_state.monthly_expenses:
        st.session_state.monthly_expenses[month_key] = []

    st.session_state.monthly_expenses[month_key].append({
        'name': name,
        'amount': float(amount),
        'date_added': datetime.now().strftime('%Y-%m-%d %H:%M')
    })


def get_month_expenses(month_key):
    """Ayın giderlerini getir"""
    return st.session_state.monthly_expenses.get(month_key, [])


def remove_expense(month_key, expense_index):
    """Gider sil"""
    if month_key in st.session_state.monthly_expenses:
        if 0 <= expense_index < len(st.session_state.monthly_expenses[month_key]):
            st.session_state.monthly_expenses[month_key].pop(expense_index)


def get_month_key_from_date_filter(selected_date_filter, start_date):
    """Tarih filtresinden ay anahtarı oluştur"""
    if selected_date_filter == "All Time":
        return datetime.now().strftime('%Y-%m')
    else:
        return start_date.strftime('%Y-%m') if start_date else datetime.now().strftime('%Y-%m')


# =================== MAIN DASHBOARD CONTENT ===================

def main_dashboard_content():
    """Ana dashboard içeriği - Auth korumalı"""

    # Sayfa konfigürasyonu
    st.set_page_config(
        page_title="Dashboard",
        page_icon="📊",
        layout="wide"
    )

    st.title("📊 Main Dashboard")

    # Logout option'ı göster
    show_logout_option()

    # Cache'li veri alma fonksiyonu
    @st.cache_data(ttl=300)  # 5 dakika cache
    def get_cached_data():
        """Cache'li veri alma"""
        return get_all_data()

    # Sayfa yenileme butonu
    col1, col2, col3 = st.columns([6, 1, 1])
    with col2:
        if st.button("🔄 Refresh"):
            st.cache_data.clear()
            st.rerun()

    # Veri yükleme
    try:
        data = get_cached_data()
    except Exception as e:
        st.error(f"❌ Data loading error: {str(e)}")
        data = []

    if not data:
        st.info("📊 No data available. Upload data from Data Management page.")

        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("📁 Go to Data Management", type="primary", use_container_width=True):
                st.switch_page("pages/3_Data_Management.py")
        st.stop()

    # DataFrame'e dönüştür ve temizle
    try:
        df = pd.DataFrame(data)
        df = clean_dataframe(df)
        df, date_columns_converted = convert_date_columns(df)

        st.success(f"✅ {len(df)} records loaded")
    except Exception as e:
        st.error(f"❌ Data processing error: {str(e)}")
        st.stop()

    # Business Metrics with integrated date filter
    st.subheader("📈 Business Metrics")

    # Date filter controls (integrated with business metrics)
    if date_columns_converted:
        col1, col2, col3, col4 = st.columns([2, 2, 2, 2])

        with col1:
            # Date column selection
            date_filter_options = ["All Time"] + date_columns_converted
            selected_date_filter = st.selectbox("📅 Filter by:", date_filter_options)

        # Show date range selectors only if a date column is selected
        if selected_date_filter != "All Time":
            with col2:
                start_date = st.date_input(
                    "From:",
                    value=df[selected_date_filter].min().date() if df[selected_date_filter].notna().any()
                    else datetime.now().date() - timedelta(days=30)
                )
            with col3:
                end_date = st.date_input(
                    "To:",
                    value=df[selected_date_filter].max().date() if df[selected_date_filter].notna().any()
                    else datetime.now().date()
                )

            # Apply date filter
            if start_date and end_date:
                df_filtered = apply_date_filter(df, selected_date_filter, start_date, end_date)

                if len(df_filtered) != len(df):
                    with col4:
                        st.info(f"📊 Filtered: {len(df_filtered)}/{len(df)} records")
                    df = df_filtered
        else:
            # Show total records when "All Time" is selected
            with col2:
                st.info(f"📊 Total: {len(df)} records")

    # Calculate and display metrics
    try:
        metrics = calculate_metrics(df)

        # Main metrics row
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("📊 Total Orders", metrics['total_orders'])
        col2.metric("💰 Total Profit", f"${metrics['total_profit']:,.2f}")
        col3.metric("📈 ROI", f"{metrics['roi']:.1f}%")
        col4.metric("📊 Margin", f"{metrics['margin']:.1f}%")

        # Secondary metrics row
        col1, col2, col3 = st.columns(3)
        col1.metric("✅ Profitable Orders", metrics['profitable_orders'])
        col2.metric("❌ Loss Orders", metrics['loss_orders'])
        col3.metric("⚪ Breakeven", metrics['breakeven_orders'])
    except Exception as e:
        st.error(f"❌ Metrics calculation error: {str(e)}")

    # =================== MONTHLY EXPENSES SECTION (SESSION STATE) ===================
    st.markdown("---")

    # Current month determination
    current_month_key = get_month_key_from_date_filter(
        selected_date_filter if 'selected_date_filter' in locals() else "All Time",
        start_date if 'start_date' in locals() else None
    )

    # Month display name
    month_display = datetime.strptime(current_month_key, '%Y-%m').strftime('%B %Y')

    col1, col2 = st.columns([3, 1])

    with col1:
        st.subheader(f"💰 Monthly Expenses - {month_display}")

    with col2:
        include_expenses = st.checkbox("Include in Profit Calculation", key="include_expenses")

    # Get current month expenses
    current_expenses = get_month_expenses(current_month_key)
    total_expenses = sum(expense['amount'] for expense in current_expenses)

    # Show current expenses if any exist
    if current_expenses:
        st.write("**Current Expenses:**")

        col1, col2, col3 = st.columns([3, 2, 1])

        for i, expense in enumerate(current_expenses):
            with col1:
                st.write(f"• {expense['name']}")
            with col2:
                st.write(f"${expense['amount']:.2f}")
            with col3:
                if st.button("🗑️", key=f"del_{current_month_key}_{i}", help="Delete expense"):
                    remove_expense(current_month_key, i)
                    st.rerun()

        st.markdown(f"**Total Expenses: ${total_expenses:.2f}**")
    else:
        st.info("No expenses added for this month yet.")

    # Add new expense
    st.markdown("**Add New Expense:**")
    col1, col2, col3 = st.columns([3, 2, 1])

    with col1:
        expense_name = st.text_input("Expense Name", placeholder="e.g., Bogahost, Ads, Tools...",
                                     key="new_expense_name")

    with col2:
        expense_amount = st.number_input("Amount ($)", min_value=0.01, step=0.01, key="new_expense_amount")

    with col3:
        st.write("")  # Spacer
        if st.button("➕ Add", type="primary", key="add_expense_btn"):
            if expense_name and expense_amount > 0:
                add_expense_to_month(current_month_key, expense_name, expense_amount)
                st.success(f"Added {expense_name}: ${expense_amount:.2f}")
                st.rerun()
            else:
                st.error("Please enter both name and amount")

    # Show adjusted metrics if expenses are included
    if include_expenses and total_expenses > 0:
        st.markdown("---")
        st.subheader("📊 Adjusted Metrics (Including Expenses)")

        try:
            # Recalculate metrics with expenses
            original_profit = metrics['total_profit'] if 'metrics' in locals() else 0
            adjusted_profit = original_profit - total_expenses

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric(
                    "📊 Original Profit",
                    f"${original_profit:,.2f}",
                    help="Profit without monthly expenses"
                )

            with col2:
                st.metric(
                    "💸 Monthly Expenses",
                    f"-${total_expenses:,.2f}",
                    help="Total expenses for this month"
                )

            with col3:
                st.metric(
                    "💰 Adjusted Profit",
                    f"${adjusted_profit:,.2f}",
                    delta=f"${-total_expenses:.2f}",
                    help="Profit after deducting monthly expenses"
                )

            with col4:
                expense_ratio = (total_expenses / original_profit * 100) if original_profit > 0 else 0
                st.metric(
                    "📈 Expense Ratio",
                    f"{expense_ratio:.1f}%",
                    help="Expenses as percentage of profit"
                )

            # Additional insights
            if expense_ratio > 0:
                if expense_ratio < 10:
                    st.success("✅ Good expense ratio! Under 10%")
                elif expense_ratio < 20:
                    st.warning("⚠️ Moderate expense ratio. Consider optimization.")
                else:
                    st.error("🚨 High expense ratio! Review your expenses.")

        except Exception as e:
            st.error(f"Error calculating adjusted metrics: {str(e)}")

    # Quick expense templates (bonus feature)
    with st.expander("🚀 Quick Templates"):
        st.write("**Common Expense Templates:**")

        col1, col2, col3 = st.columns(3)

        templates = {
            "Basic": [
                {"name": "Bogahost", "amount": 200},
                {"name": "Basic Tools", "amount": 100}
            ],
            "Marketing": [
                {"name": "Bogahost", "amount": 200},
                {"name": "Facebook Ads", "amount": 300},
                {"name": "Google Ads", "amount": 250}
            ],
            "Premium": [
                {"name": "Bogahost", "amount": 200},
                {"name": "Premium Tools", "amount": 300},
                {"name": "Marketing", "amount": 400},
                {"name": "VA Payments", "amount": 500}
            ]
        }

        for i, (template_name, template_expenses) in enumerate(templates.items()):
            with [col1, col2, col3][i]:
                st.write(f"**{template_name}**")
                total_template = sum(exp['amount'] for exp in template_expenses)
                st.write(f"Total: ${total_template}")

                for exp in template_expenses:
                    st.write(f"• {exp['name']}: ${exp['amount']}")

                if st.button(f"Apply {template_name}", key=f"template_{template_name}"):
                    for exp in template_expenses:
                        add_expense_to_month(current_month_key, exp['name'], exp['amount'])
                    st.success(f"Applied {template_name} template!")
                    st.rerun()

    # Debug info (can be removed later)
    if st.sidebar.checkbox("🔧 Debug Mode"):
        st.sidebar.write("**Session State Debug:**")
        st.sidebar.write(f"Current Month: {current_month_key}")
        st.sidebar.write("All Expenses:")
        st.sidebar.json(st.session_state.monthly_expenses)

    # =================== TOP PRODUCTS & DATA TABLE ===================

    # En iyi ürünler
    product_columns = [col for col in df.columns if any(keyword in col.lower()
                                                        for keyword in ['title', 'product', 'item', 'asin'])]

    profit_columns = [col for col in df.columns if 'profit' in col.lower()]

    if product_columns and profit_columns:
        st.subheader("🏆 Top Products")

        product_col = st.selectbox("Select product column:", product_columns)
        profit_col = st.selectbox("Select profit column:", profit_columns)

        if product_col in df.columns and profit_col in df.columns:
            try:
                top_products = df.groupby(product_col)[profit_col].agg(['sum', 'count', 'mean']).round(2)
                top_products.columns = ['Total Profit', 'Order Count', 'Average Profit']
                top_products = top_products.sort_values('Total Profit', ascending=False).head(10)

                st.dataframe(top_products, use_container_width=True)
            except Exception as e:
                st.warning(f"⚠️ Top products error: {str(e)}")

    # Ham veri tablosu
    st.subheader("📋 Data Table")

    try:
        display_columns = filter_columns_for_display(df)
        column_names = get_column_display_names(display_columns)

        selected_columns = st.multiselect(
            "Select columns to display:",
            options=display_columns,
            default=display_columns[:10] if len(display_columns) > 10 else display_columns,
            format_func=lambda x: column_names.get(x, x)
        )

        if selected_columns:
            # Sayfa boyutu
            page_size = st.selectbox("Page size:", [10, 25, 50, 100], index=1)

            # Sayfalama
            total_rows = len(df)
            total_pages = (total_rows - 1) // page_size + 1

            if total_pages > 1:
                page_number = st.number_input(
                    f"Page (1-{total_pages}):",
                    min_value=1,
                    max_value=total_pages,
                    value=1
                )

                start_idx = (page_number - 1) * page_size
                end_idx = start_idx + page_size

                st.info(
                    f"📄 Page {page_number}/{total_pages} - Records {start_idx + 1}-{min(end_idx, total_rows)} / {total_rows}")
                df_page = df.iloc[start_idx:end_idx]
            else:
                df_page = df

            # Formatted table
            df_display = format_money_columns(df_page, selected_columns)
            st.dataframe(df_display, use_container_width=True)

    except Exception as e:
        st.error(f"❌ Table display error: {str(e)}")

    # Footer
    st.markdown("---")
    st.caption(f"📊 Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


# =================== MAIN EXECUTION ===================

def main():
    """Ana fonksiyon - Auth kontrolü ile"""

    # Auth kontrolü
    is_authenticated, _ = check_authentication()

    if not is_authenticated:
        # Login sayfası göster
        show_login_page()
    else:
        # Ana dashboard'u göster
        main_dashboard_content()


# Run the app
if __name__ == "__main__":
    main()
else:
    # Streamlit import edildiğinde otomatik çalıştır
    main()