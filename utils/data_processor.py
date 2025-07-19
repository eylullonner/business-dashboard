import pandas as pd
import streamlit as st
import re
from config import (
    NUMERIC_FIELDS, EXCLUDED_COLUMNS, DATE_COLUMNS,
    PRIORITY_DISPLAY_COLUMNS, COLUMN_DISPLAY_NAMES,
    ACCOUNT_SETTINGS, BUSINESS_METRICS, ACCOUNT_PERFORMANCE_CONFIG
)


def clean_dataframe(df):
    """DataFrame'i temizle ve optimize et"""
    if df.empty:
        return df

    # Numeric alanları dönüştür
    for field in NUMERIC_FIELDS:
        if field in df.columns:
            df[field] = pd.to_numeric(df[field], errors='coerce').fillna(0)

    # Boş string'leri NaN ile değiştir
    df = df.replace('', pd.NA)

    # Amazon account field'ı için default value
    if 'amazon_account' in df.columns:
        df['amazon_account'] = df['amazon_account'].fillna(ACCOUNT_SETTINGS['default_account_name'])

    return df


def convert_date_columns(df):
    """Tarih kolonlarını datetime'a çevir"""
    date_columns_converted = []

    for key, col_name in DATE_COLUMNS.items():
        if col_name in df.columns:
            try:
                df[col_name] = pd.to_datetime(df[col_name], errors='coerce')
                date_columns_converted.append(col_name)
            except Exception as e:
                st.warning(f"⚠️ Could not convert {col_name} to date: {str(e)}")

    return df, date_columns_converted


def filter_columns_for_display(df):
    """Görüntüleme için kolonları filtrele ve sırala - UPDATED: Account priority"""
    if df.empty:
        return []

    # Tüm mevcut kolonları al ve istenmeyen kolonları çıkar
    all_columns = [col for col in df.columns if col not in EXCLUDED_COLUMNS]

    # Priority columnları önce sırala - amazon_account dahil
    ordered_columns = []
    for col in PRIORITY_DISPLAY_COLUMNS:
        if col in all_columns:
            ordered_columns.append(col)
            all_columns.remove(col)

    # Kalan kolonları ekle
    ordered_columns.extend(all_columns)

    return ordered_columns


def get_column_display_names(columns):
    """Kolon isimlerini daha okunabilir hale getir - UPDATED: Account field dahil"""
    column_display_names = {}

    for col in columns:
        # Önce config'den kontrol et
        if col in COLUMN_DISPLAY_NAMES:
            column_display_names[col] = COLUMN_DISPLAY_NAMES[col]
        else:
            # Kolon isimlerini güzelleştir
            display_name = col.replace('_', ' ').title()
            if 'usd' in col.lower():
                display_name = display_name.replace('Usd', '($)')
            if 'amazon_account' in col.lower():
                display_name = 'Amazon Account'
            column_display_names[col] = display_name

    return column_display_names


def apply_date_filter(df, selected_date_col, start_date, end_date):
    """Tarih filtresini uygula"""
    try:
        # Tarih tipini kontrol et
        if not pd.api.types.is_datetime64_any_dtype(df[selected_date_col]):
            st.warning(f"⚠️ {selected_date_col} is not a datetime column")
            return df

        filtered_df = df[
            (df[selected_date_col].dt.date >= start_date) &
            (df[selected_date_col].dt.date <= end_date)
            ]
        return filtered_df
    except Exception as e:
        st.error(f"❌ Date filter error: {str(e)}")
        return df


def apply_account_filter(df, account_filter_type, selected_accounts=None):
    """Account bazında filtreleme - YENİ FONKSIYON"""
    if df.empty or 'amazon_account' not in df.columns:
        return df

    try:
        if account_filter_type == "all_accounts":
            return df

        elif account_filter_type == "specific_account" and selected_accounts:
            if isinstance(selected_accounts, str):
                selected_accounts = [selected_accounts]
            return df[df['amazon_account'].isin(selected_accounts)]

        elif account_filter_type == "top_performing":
            # Top 5 performing accounts by total profit
            account_profits = df.groupby('amazon_account')['calculated_profit_usd'].sum()
            top_accounts = account_profits.nlargest(5).index.tolist()
            return df[df['amazon_account'].isin(top_accounts)]

        return df

    except Exception as e:
        st.error(f"❌ Account filter error: {str(e)}")
        return df


def calculate_metrics(df):
    """İş metriklerini hesapla - UPDATED: Account breakdown dahil"""
    if df.empty:
        return {
            'total_orders': 0,
            'total_profit': 0,
            'total_cost': 0,
            'total_revenue': 0,
            'roi': 0,
            'margin': 0,
            'profitable_orders': 0,
            'loss_orders': 0,
            'breakeven_orders': 0,
            'account_breakdown': {}
        }

    total_orders = len(df)

    # Profit hesaplama
    total_profit = 0
    if 'calculated_profit_usd' in df.columns:
        total_profit = df['calculated_profit_usd'].sum()

    # Cost hesaplama
    total_cost = 0
    if 'calculated_amazon_cost_usd' in df.columns:
        total_cost = df['calculated_amazon_cost_usd'].sum()

    # Revenue hesaplama
    total_revenue = 0
    if 'calculated_ebay_earning_usd' in df.columns:
        total_revenue = df['calculated_ebay_earning_usd'].sum()

    # ROI ve Margin hesaplama
    roi = (total_profit / total_cost * 100) if total_cost > 0 else 0
    margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0

    # Kârlı/zararlı sipariş hesaplama
    profitable_orders = 0
    loss_orders = 0
    breakeven_orders = 0

    if 'calculated_profit_usd' in df.columns:
        profitable_orders = len(df[df['calculated_profit_usd'] > 0])
        loss_orders = len(df[df['calculated_profit_usd'] < 0])
        breakeven_orders = len(df[df['calculated_profit_usd'] == 0])

    # Account breakdown - YENİ EKLENEN
    account_breakdown = {}
    if 'amazon_account' in df.columns:
        account_breakdown = calculate_account_breakdown(df)

    return {
        'total_orders': total_orders,
        'total_profit': total_profit,
        'total_cost': total_cost,
        'total_revenue': total_revenue,
        'roi': roi,
        'margin': margin,
        'profitable_orders': profitable_orders,
        'loss_orders': loss_orders,
        'breakeven_orders': breakeven_orders,
        'account_breakdown': account_breakdown
    }


def calculate_account_breakdown(df):
    """Account bazında detaylı metrics hesapla - YENİ FONKSIYON"""
    if df.empty or 'amazon_account' not in df.columns:
        return {}

    try:
        # Account bazında gruplama
        account_groups = df.groupby('amazon_account')

        breakdown = {}

        for account, group in account_groups:
            account_metrics = {
                'total_orders': len(group),
                'total_profit': group['calculated_profit_usd'].sum() if 'calculated_profit_usd' in group.columns else 0,
                'total_cost': group[
                    'calculated_amazon_cost_usd'].sum() if 'calculated_amazon_cost_usd' in group.columns else 0,
                'total_revenue': group[
                    'calculated_ebay_earning_usd'].sum() if 'calculated_ebay_earning_usd' in group.columns else 0,
                'average_profit': group[
                    'calculated_profit_usd'].mean() if 'calculated_profit_usd' in group.columns else 0,
                'profitable_orders': len(
                    group[group['calculated_profit_usd'] > 0]) if 'calculated_profit_usd' in group.columns else 0,
                'loss_orders': len(
                    group[group['calculated_profit_usd'] < 0]) if 'calculated_profit_usd' in group.columns else 0
            }

            # ROI hesaplama
            if account_metrics['total_cost'] > 0:
                account_metrics['roi'] = (account_metrics['total_profit'] / account_metrics['total_cost']) * 100
            else:
                account_metrics['roi'] = 0

            # Margin hesaplama
            if account_metrics['total_revenue'] > 0:
                account_metrics['margin'] = (account_metrics['total_profit'] / account_metrics['total_revenue']) * 100
            else:
                account_metrics['margin'] = 0

            # Success rate hesaplama
            if account_metrics['total_orders'] > 0:
                account_metrics['success_rate'] = (account_metrics['profitable_orders'] / account_metrics[
                    'total_orders']) * 100
            else:
                account_metrics['success_rate'] = 0

            # Performance rating hesaplama
            account_metrics['performance_rating'] = calculate_account_performance_rating(account_metrics)

            breakdown[account] = account_metrics

        return breakdown

    except Exception as e:
        st.error(f"❌ Account breakdown calculation error: {str(e)}")
        return {}


def calculate_account_performance_rating(account_metrics):
    """Account performance rating hesapla - YENİ FONKSIYON"""
    try:
        criteria = ACCOUNT_PERFORMANCE_CONFIG['rating_criteria']

        # Normalize values to 0-100 scale
        profit_score = min(100, max(0, account_metrics['total_profit'] / 10))  # $1000 = 100 points
        roi_score = min(100, max(0, account_metrics['roi'] * 2))  # 50% ROI = 100 points
        order_score = min(100, max(0, account_metrics['total_orders'] * 5))  # 20 orders = 100 points
        success_score = account_metrics['success_rate']  # Already 0-100

        # Weighted average
        total_score = (
                profit_score * criteria['total_profit'] +
                roi_score * criteria['average_roi'] +
                order_score * criteria['order_count'] +
                success_score * criteria['success_rate']
        )

        # Get rating
        from config import get_performance_rating
        rating, label, color = get_performance_rating(total_score)

        return {
            'score': round(total_score, 1),
            'rating': rating,
            'label': label,
            'color': color
        }

    except Exception as e:
        return {
            'score': 0,
            'rating': 'D',
            'label': 'Poor',
            'color': '#C0392B'
        }


def format_money_columns(df, selected_columns):
    """Para formatını uygula"""
    if df.empty:
        return df

    display_df = df[selected_columns].copy()

    # Para formatı (USD içeren kolonlar için)
    money_cols = [col for col in selected_columns if 'usd' in col.lower()]
    for col in money_cols:
        if col in display_df.columns:
            display_df[col] = display_df[col].apply(
                lambda x: f"${x:.2f}" if pd.notnull(x) and x != 0 else "$0.00"
            )

    return display_df


def format_account_column(df, account_column='amazon_account'):
    """Account kolonunu format et - badges/colors ekle - YENİ FONKSIYON"""
    if df.empty or account_column not in df.columns:
        return df

    display_df = df.copy()

    # Account name'leri temizle ve formatla
    display_df[account_column] = display_df[account_column].apply(
        lambda x: str(x).title() if pd.notnull(x) else 'Unknown'
    )

    return display_df


def get_account_summary_stats(df):
    """Account summary istatistikleri - YENİ FONKSIYON"""
    if df.empty or 'amazon_account' not in df.columns:
        return {}

    try:
        unique_accounts = df['amazon_account'].nunique()
        total_orders = len(df)

        # En başarılı account
        if 'calculated_profit_usd' in df.columns:
            account_profits = df.groupby('amazon_account')['calculated_profit_usd'].sum()
            top_account = account_profits.idxmax()
            top_account_profit = account_profits.max()
        else:
            top_account = "N/A"
            top_account_profit = 0

        # En çok sipariş olan account
        account_orders = df.groupby('amazon_account').size()
        most_active_account = account_orders.idxmax()
        most_active_orders = account_orders.max()

        return {
            'total_accounts': unique_accounts,
            'total_orders': total_orders,
            'avg_orders_per_account': round(total_orders / unique_accounts, 1),
            'top_profit_account': top_account,
            'top_profit_amount': top_account_profit,
            'most_active_account': most_active_account,
            'most_active_orders': most_active_orders
        }

    except Exception as e:
        st.error(f"❌ Account summary error: {str(e)}")
        return {}


def get_data_summary(df):
    """Veri özeti çıkar - UPDATED: Account info dahil"""
    if df.empty:
        return {}

    # Basic summary
    summary = {
        'total_records': len(df),
        'total_columns': len(df.columns),
        'numeric_columns': len(df.select_dtypes(include=['number']).columns),
        'date_columns': len(df.select_dtypes(include=['datetime']).columns),
        'text_columns': len(df.select_dtypes(include=['object']).columns),
        'memory_usage': f"{df.memory_usage(deep=True).sum() / 1024 / 1024:.2f} MB"
    }

    # Account-specific summary
    if 'amazon_account' in df.columns:
        account_summary = get_account_summary_stats(df)
        summary.update(account_summary)

    return summary


def validate_data_quality(df):
    """Veri kalitesini kontrol et - UPDATED: Account validation dahil"""
    if df.empty:
        return []

    issues = []

    # Boş değer kontrolü
    null_counts = df.isnull().sum()
    high_null_cols = null_counts[null_counts > len(df) * 0.5]
    if not high_null_cols.empty:
        issues.append(f"High null values in columns: {list(high_null_cols.index)}")

    # Duplicate kontrol - composite key (amazon_orderid + amazon_account)
    if 'amazon_orderid' in df.columns and 'amazon_account' in df.columns:
        duplicates = df.duplicated(subset=['amazon_orderid', 'amazon_account']).sum()
        if duplicates > 0:
            issues.append(f"Found {duplicates} duplicate records (same orderid + account)")
    else:
        # Fallback - sadece orderid
        if 'amazon_orderid' in df.columns:
            duplicates = df.duplicated(subset=['amazon_orderid']).sum()
            if duplicates > 0:
                issues.append(f"Found {duplicates} duplicate order IDs")

    # Amazon account validation
    if 'amazon_account' in df.columns:
        missing_accounts = df['amazon_account'].isnull().sum()
        if missing_accounts > 0:
            issues.append(f"Found {missing_accounts} records with missing amazon_account")

        # Invalid account names
        from config import validate_account_name
        invalid_accounts = df[~df['amazon_account'].apply(validate_account_name)]['amazon_account'].nunique()
        if invalid_accounts > 0:
            issues.append(f"Found {invalid_accounts} records with invalid account names")

    # Numeric kolonlarda negatif değer kontrolü
    for col in NUMERIC_FIELDS:
        if col in df.columns:
            negative_count = (df[col] < 0).sum()
            if negative_count > 0:
                issues.append(f"Found {negative_count} negative values in {col}")

    return issues


def prepare_export_data(df, include_account_breakdown=True):
    """Export için veriyi hazırla - YENİ FONKSIYON"""
    if df.empty:
        return {}

    export_data = {
        'main_data': df.to_dict('records'),
        'summary': get_data_summary(df),
        'quality_issues': validate_data_quality(df)
    }

    if include_account_breakdown and 'amazon_account' in df.columns:
        # Account bazında ayrı sheets/sections
        account_data = {}
        for account in df['amazon_account'].unique():
            account_df = df[df['amazon_account'] == account]
            account_data[account] = {
                'data': account_df.to_dict('records'),
                'metrics': calculate_account_breakdown(
                    account_df.to_frame().T if len(account_df) == 1 else account_df).get(account, {})
            }

        export_data['account_breakdown'] = account_data

    return export_data


def get_account_color_mapping(df):
    """Account'lar için consistent color mapping - YENİ FONKSIYON"""
    if df.empty or 'amazon_account' not in df.columns:
        return {}

    from config import get_account_color

    unique_accounts = sorted(df['amazon_account'].unique())
    color_mapping = {}

    for i, account in enumerate(unique_accounts):
        color_mapping[account] = get_account_color(account, i)

    return color_mapping


def filter_by_performance_level(df, performance_levels=['A+', 'A']):
    """Performance level'a göre filtreleme - YENİ FONKSIYON"""
    if df.empty or 'amazon_account' not in df.columns:
        return df

    try:
        account_breakdown = calculate_account_breakdown(df)

        # High-performing accounts
        good_accounts = []
        for account, metrics in account_breakdown.items():
            if metrics['performance_rating']['rating'] in performance_levels:
                good_accounts.append(account)

        return df[df['amazon_account'].isin(good_accounts)]

    except Exception as e:
        st.error(f"❌ Performance filtering error: {str(e)}")
        return df


def create_account_comparison_data(df):
    """Account karşılaştırma için data hazırla - YENİ FONKSIYON"""
    if df.empty or 'amazon_account' not in df.columns:
        return pd.DataFrame()

    try:
        account_breakdown = calculate_account_breakdown(df)

        comparison_data = []
        for account, metrics in account_breakdown.items():
            comparison_data.append({
                'Account': account,
                'Total Orders': metrics['total_orders'],
                'Total Profit ($)': round(metrics['total_profit'], 2),
                'Average Profit ($)': round(metrics['average_profit'], 2),
                'ROI (%)': round(metrics['roi'], 1),
                'Margin (%)': round(metrics['margin'], 1),
                'Success Rate (%)': round(metrics['success_rate'], 1),
                'Performance Rating': metrics['performance_rating']['rating'],
                'Rating Score': metrics['performance_rating']['score']
            })

        return pd.DataFrame(comparison_data).sort_values('Total Profit ($)', ascending=False)

    except Exception as e:
        st.error(f"❌ Comparison data creation error: {str(e)}")
        return pd.DataFrame()


def calculate_single_order_profit(ebay_data: dict, amazon_data: dict) -> dict:
    """
    Tek sipariş için kâr metriklerini hesapla - Order Matcher'dan taşındı
    Exchange rate handling, TRY→USD conversion, ROI, return detection dahil
    """
    try:
        # Exchange rate handler'ı import et (opsiyonel)
        try:
            import sys, os
            sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from utils.exchange_rate_handler import ExchangeRateHandler
            rate_handler = ExchangeRateHandler()
        except ImportError:
            rate_handler = None

        # eBay geliri
        ebay_earning = 0.0
        for field in ['Order earnings', 'order_earnings', 'earnings', 'profit', 'revenue']:
            if field in ebay_data and pd.notna(ebay_data[field]):
                try:
                    ebay_earning = float(ebay_data[field])
                    break
                except (ValueError, TypeError):
                    continue

        # Return Detection - Amazon iade kontrolü
        possible_fields = [
            'deliveryStatus',
            'amazon_deliverystatus',
            'amazon_delivery_status',
            'amazon_status',
            'deliverystatus',
            'delivery_status',
            'status'
        ]

        delivery_status_raw = ''
        for field in possible_fields:
            if field in amazon_data and amazon_data[field]:
                delivery_status_raw = amazon_data[field]
                break

        delivery_status = str(delivery_status_raw).strip().lower()
        return_keywords = ['returned', 'refunded', 'refund', 'cancelled', 'return complete']
        is_returned = any(keyword in delivery_status for keyword in return_keywords)

        # Amazon maliyeti hesaplama - Return detection öncelikli
        amazon_cost_usd = 0.0
        cost_calculation_method = "unknown"
        actual_exchange_rate = None

        if is_returned:
            # Ürün iade edilmişse cost = 0
            amazon_cost_usd = 0.0
            cost_calculation_method = "return_detected_cost_zero"
        else:
            # Normal cost calculation - 4 YÖNTEMLİ + KUR BİLGİSİ
            order_total = amazon_data.get('orderTotal') or amazon_data.get('grand_total', '')

            # PRIORITY 1: USD Direct
            if order_total and ('USD' in str(order_total) or '$' in str(order_total)):
                usd_amount = parse_usd_amount(str(order_total))
                if usd_amount > 0:
                    amazon_cost_usd = usd_amount
                    cost_calculation_method = "usd_direct_no_conversion"

            # PRIORITY 2: TRY + API (KUR BİLGİSİ ALMA)
            elif order_total and 'TRY' in str(order_total) and rate_handler:
                order_date = amazon_data.get('orderDate') or amazon_data.get('order_date', '')

                if order_date:
                    success, calculated_cost, calc_message = rate_handler.calculate_amazon_cost_usd(
                        order_total, order_date
                    )

                    if success:
                        amazon_cost_usd = calculated_cost

                        # GERÇEK KUR BİLGİSİNİ AL
                        try_amount = parse_usd_amount(order_total)  # TRY miktarı
                        if try_amount > 0 and calculated_cost > 0:
                            actual_exchange_rate = round(try_amount / calculated_cost, 2)
                            cost_calculation_method = f"api_rate_{actual_exchange_rate}_try_per_usd"
                        else:
                            cost_calculation_method = "api_conversion_success"

            # PRIORITY 3: Existing USD Field
            if amazon_cost_usd == 0.0:  # Yukarıdakiler başarısızsa
                for field in ['amazon_cost_usd', 'Amazon cost USD', 'cost_usd', 'usd_cost']:
                    if field in amazon_data and pd.notna(amazon_data[field]):
                        amazon_cost_str = str(amazon_data[field])
                        if amazon_cost_str and amazon_cost_str != 'Not available':
                            parsed_usd = parse_usd_amount(amazon_cost_str)
                            if parsed_usd > 0:
                                amazon_cost_usd = parsed_usd
                                cost_calculation_method = "existing_usd_field"
                                break

            # PRIORITY 4: Sabit Kur Fallback (KUR BİLGİSİ)
            if amazon_cost_usd == 0.0 and order_total and 'TRY' in str(order_total):
                try_amount = parse_usd_amount(order_total)  # TRY parse eder
                if try_amount > 0:
                    # Sabit kur kullan (güncel TRY/USD ~34)
                    FALLBACK_RATE = 34.0  # 1 USD = 34 TRY
                    amazon_cost_usd = try_amount / FALLBACK_RATE
                    actual_exchange_rate = FALLBACK_RATE
                    cost_calculation_method = f"fallback_rate_{FALLBACK_RATE}_try_per_usd"

        # Hesaplamalar
        profit_usd = ebay_earning - amazon_cost_usd
        margin_percent = (profit_usd / ebay_earning * 100) if ebay_earning > 0 else 0

        # ROI hesaplaması: (Profit / Investment) * 100
        # Investment = Amazon cost (ne kadar para harcadık)
        roi_percent = (profit_usd / amazon_cost_usd * 100) if amazon_cost_usd > 0 else 0

        return {
            'calculated_ebay_earning_usd': round(ebay_earning, 2),
            'calculated_amazon_cost_usd': round(amazon_cost_usd, 2),
            'calculated_profit_usd': round(profit_usd, 2),
            'calculated_margin_percent': round(margin_percent, 2),
            'calculated_roi_percent': round(roi_percent, 2),
            'cost_calculation_method': cost_calculation_method,
            'exchange_rate_used': actual_exchange_rate
        }

    except Exception as e:
        return {
            'calculated_ebay_earning_usd': 0.0,
            'calculated_amazon_cost_usd': 0.0,
            'calculated_profit_usd': 0.0,
            'calculated_margin_percent': 0.0,
            'calculated_roi_percent': 0.0,
            'cost_calculation_method': f"error: {str(e)}",
            'exchange_rate_used': None
        }


def parse_usd_amount(amount_string: str) -> float:
    """USD/TRY string'ini float'a çevir - Order Matcher'dan taşındı"""
    if not amount_string or pd.isna(amount_string):
        return 0.0

    amount_str = str(amount_string).strip()

    # USD için: "$25.50", "USD 25.50", "25.50 USD"
    if 'USD' in amount_str or '$' in amount_str:
        clean_str = amount_str.replace('USD', '').replace('$', '').strip()
    else:
        # TRY için: "TRY 693.08", "693.08 TRY", "₺693.08"
        clean_str = amount_str.replace('TRY', '').replace('₺', '').strip()

    # Virgülleri handle et
    if ',' in clean_str and '.' in clean_str:
        clean_str = clean_str.replace(',', '')
    elif ',' in clean_str and '.' not in clean_str:
        clean_str = clean_str.replace(',', '.')

    # Sayıları extract et
    numbers = re.findall(r'\d+\.?\d*', clean_str)
    if numbers:
        try:
            return float(numbers[-1])
        except ValueError:
            return 0.0

    return 0.0