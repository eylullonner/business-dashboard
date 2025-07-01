import pandas as pd
import streamlit as st
from config import NUMERIC_FIELDS, EXCLUDED_COLUMNS, DATE_COLUMNS


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
    """Görüntüleme için kolonları filtrele ve sırala"""
    if df.empty:
        return []

    # Tüm mevcut kolonları al ve istenmeyen kolonları çıkar
    all_columns = [col for col in df.columns if col not in EXCLUDED_COLUMNS]

    # Önemli kolonları önce sırala
    priority_columns = [
        'master_no', 'ebay_order_number', 'amazon_order_number',
        'calculated_profit_usd', 'calculated_ebay_earning_usd', 'calculated_amazon_cost_usd'
    ]

    # Öncelikli kolonları başa al
    ordered_columns = []
    for col in priority_columns:
        if col in all_columns:
            ordered_columns.append(col)
            all_columns.remove(col)

    # Kalan kolonları ekle
    ordered_columns.extend(all_columns)

    return ordered_columns


def get_column_display_names(columns):
    """Kolon isimlerini daha okunabilir hale getir"""
    from config import COLUMN_DISPLAY_NAMES

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


def calculate_metrics(df):
    """İş metriklerini hesapla"""
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
            'breakeven_orders': 0
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

    return {
        'total_orders': total_orders,
        'total_profit': total_profit,
        'total_cost': total_cost,
        'total_revenue': total_revenue,
        'roi': roi,
        'margin': margin,
        'profitable_orders': profitable_orders,
        'loss_orders': loss_orders,
        'breakeven_orders': breakeven_orders
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


def get_data_summary(df):
    """Veri özeti çıkar"""
    if df.empty:
        return {}

    summary = {
        'total_records': len(df),
        'total_columns': len(df.columns),
        'numeric_columns': len(df.select_dtypes(include=['number']).columns),
        'date_columns': len(df.select_dtypes(include=['datetime']).columns),
        'text_columns': len(df.select_dtypes(include=['object']).columns),
        'memory_usage': f"{df.memory_usage(deep=True).sum() / 1024 / 1024:.2f} MB"
    }

    return summary


def validate_data_quality(df):
    """Veri kalitesini kontrol et"""
    if df.empty:
        return []

    issues = []

    # Boş değer kontrolü
    null_counts = df.isnull().sum()
    high_null_cols = null_counts[null_counts > len(df) * 0.5]
    if not high_null_cols.empty:
        issues.append(f"High null values in columns: {list(high_null_cols.index)}")

    # Duplicate kontrol
    duplicates = df.duplicated().sum()
    if duplicates > 0:
        issues.append(f"Found {duplicates} duplicate records")

    # Numeric kolonlarda negatif değer kontrolü
    for col in NUMERIC_FIELDS:
        if col in df.columns:
            negative_count = (df[col] < 0).sum()
            if negative_count > 0:
                issues.append(f"Found {negative_count} negative values in {col}")

    return issues