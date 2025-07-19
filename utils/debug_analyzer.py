# utils/debug_analyzer.py - ACCOUNT-SEPARATED VERSION
"""
Account-Separated Matching Debug Analyzer Module
Analyzes each Amazon account separately to avoid cross-account confusion
"""

import pandas as pd
import streamlit as st
from datetime import datetime
from typing import Dict, List, Tuple, Optional


class AccountSeparatedDebugAnalyzer:
    """
    Account-separated debug analyzer for order matching process
    Analyzes each Amazon account independently
    """

    def __init__(self):
        self.account_analyses = {}

    def analyze_account_separately(self, account_name: str,
                                   original_amazon_account_df: pd.DataFrame,
                                   matched_results_account_df: pd.DataFrame) -> Dict:
        """
        Analyze a single Amazon account separately

        Args:
            account_name: Name of the Amazon account
            original_amazon_account_df: Original orders for this account only
            matched_results_account_df: Matched results for this account only

        Returns:
            Dictionary with account-specific analysis
        """
        # Extract order IDs for this account
        original_orders = self.extract_order_ids_from_original_amazon(original_amazon_account_df)
        matched_orders = self.extract_order_ids_from_matched_account(matched_results_account_df)

        # Find missing orders for this account
        missing_order_ids = set(original_orders) - set(matched_orders)

        # Find duplicates within this account
        matched_series = pd.Series(matched_orders)
        duplicate_order_ids = matched_series[matched_series.duplicated()].unique()

        # Get missing order details
        missing_order_details = []
        for missing_id in missing_order_ids:
            missing_order = original_amazon_account_df[
                original_amazon_account_df['orderId'] == missing_id
                ]
            if not missing_order.empty:
                order_data = missing_order.iloc[0].to_dict()
                missing_order_details.append({
                    'order_id': missing_id,
                    'order_date': order_data.get('orderDate', 'N/A'),
                    'order_total': order_data.get('orderTotal', 'N/A'),
                    'delivery_status': order_data.get('deliveryStatus', 'N/A'),
                    'customer_name': self._extract_customer_name_from_amazon(order_data),
                    'product_title': self._extract_product_title_from_amazon(order_data),
                    'raw_data': order_data
                })

        # Get duplicate order details
        duplicate_order_details = []
        for dup_id in duplicate_order_ids:
            count = matched_series.value_counts()[dup_id]
            duplicate_matches = matched_results_account_df[
                matched_results_account_df['amazon_orderid'] == dup_id
                ]

            ebay_orders = []
            if not duplicate_matches.empty:
                ebay_orders = duplicate_matches['ebay_order_number'].tolist()

            duplicate_order_details.append({
                'order_id': dup_id,
                'count': count,
                'ebay_orders': ebay_orders,
                'details': duplicate_matches.to_dict('records') if not duplicate_matches.empty else []
            })

        return {
            'account_name': account_name,
            'original_count': len(original_orders),
            'matched_count': len(matched_orders),
            'missing_count': len(missing_order_ids),
            'duplicate_count': len(duplicate_order_ids),
            'missing_orders': missing_order_details,
            'duplicate_orders': duplicate_order_details,
            'success_rate': (len(matched_orders) / len(original_orders) * 100) if len(original_orders) > 0 else 0,
            'has_issues': len(missing_order_ids) > 0 or len(duplicate_order_ids) > 0
        }

    def extract_order_ids_from_original_amazon(self, amazon_df: pd.DataFrame) -> List[str]:
        """Extract order IDs from original Amazon DataFrame"""
        possible_fields = ['orderId', 'orderNumber', 'order_id', 'order_number', 'amazon_orderid']

        for field in possible_fields:
            if field in amazon_df.columns:
                return amazon_df[field].dropna().tolist()

        return []

    def extract_order_ids_from_matched_account(self, matched_df: pd.DataFrame) -> List[str]:
        """Extract Amazon order IDs from matched results DataFrame"""
        possible_fields = ['amazon_orderid', 'amazon_order_id', 'amazon_order_number']

        for field in possible_fields:
            if field in matched_df.columns:
                return matched_df[field].dropna().tolist()

        return []

    def _extract_customer_name_from_amazon(self, order_data: Dict) -> str:
        """Extract customer name from Amazon order data"""
        if 'shippingAddress' in order_data:
            shipping = order_data['shippingAddress']
            if isinstance(shipping, dict) and 'name' in shipping:
                return shipping['name']

        for field in ['buyer_name', 'recipient_name', 'customer_name']:
            if field in order_data and order_data[field]:
                return str(order_data[field])

        return 'N/A'

    def _extract_product_title_from_amazon(self, order_data: Dict) -> str:
        """Extract product title from Amazon order data"""
        if 'products' in order_data:
            products = order_data['products']
            if isinstance(products, list) and len(products) > 0:
                product = products[0]
                if isinstance(product, dict) and 'title' in product:
                    return product['title']

        for field in ['item_title', 'product_title', 'title']:
            if field in order_data and order_data[field]:
                return str(order_data[field])

        return 'N/A'

    def show_isolated_account_analysis(self, original_amazon_files_data: List,
                                       original_ebay_files_data: List,
                                       matched_results: pd.DataFrame):
        """
        Analyze each Amazon account as if it was matched independently
        Simulates separate matching process for each account
        """
        if matched_results.empty:
            st.warning("⚠️ No matched results to analyze")
            return

        # Check if account field exists
        if 'amazon_account' not in matched_results.columns:
            st.error("❌ No amazon_account field found in matched results")
            return

        st.markdown("#### 🏪 Isolated Account Analysis")
        st.info(
            "🔍 **Analysis Method:** Each account analyzed as if it was matched independently against all eBay orders")

        # Combine all eBay data (this would be available to each account)
        all_ebay_df = pd.DataFrame()
        for filename, ebay_df in original_ebay_files_data:
            all_ebay_df = pd.concat([all_ebay_df, ebay_df], ignore_index=True)

        # Extract account info from Amazon files
        account_original_data = {}
        for filename, amazon_df in original_amazon_files_data:
            # Extract account name from filename
            account_name = self.extract_account_from_filename(filename)
            account_original_data[account_name] = amazon_df

        # Get unique accounts from matched results
        matched_accounts = matched_results['amazon_account'].unique()

        # Overall summary first
        st.markdown("##### 📊 Overall Summary")

        total_ebay_orders = len(all_ebay_df)
        total_amazon_orders = sum(len(df) for df in account_original_data.values())
        total_matched = len(matched_results)

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total eBay Orders", total_ebay_orders)
        with col2:
            st.metric("Total Amazon Orders", total_amazon_orders)
        with col3:
            st.metric("Total Accounts", len(account_original_data))
        with col4:
            st.metric("Total Matches", total_matched)

        # Analyze each account independently
        st.markdown("##### 🔍 Independent Account Analysis")

        account_summaries = []

        for account_name, original_amazon_df in account_original_data.items():

            # Get matched results for this account only
            account_matched_df = matched_results[
                matched_results['amazon_account'] == account_name
                ]

            # Simulate independent matching scenario
            analysis = self.simulate_independent_matching(
                account_name=account_name,
                ebay_orders_available=all_ebay_df,
                amazon_orders_this_account=original_amazon_df,
                actual_matches_this_account=account_matched_df
            )

            account_summaries.append(analysis)

            # Display account analysis
            status_icon = "❌" if analysis['has_issues'] else "✅"
            issues_text = ""

            if analysis['missing_count'] > 0:
                issues_text += f" | Missing: {analysis['missing_count']}"
            if analysis['duplicate_count'] > 0:
                issues_text += f" | Duplicates: {analysis['duplicate_count']}"

            with st.expander(f"{status_icon} **{account_name}**{issues_text}"):

                # Account metrics
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric("Available eBay", analysis['available_ebay_orders'])

                with col2:
                    st.metric("Amazon Orders", analysis['amazon_orders'])

                with col3:
                    st.metric("Actual Matches", analysis['actual_matches'])

                # Missing Amazon orders (didn't match any eBay)
                if analysis['missing_orders']:
                    st.markdown("**🔍 Amazon Orders That Didn't Match Any eBay:**")

                    missing_df = pd.DataFrame([
                        {
                            'Amazon Order ID': order['order_id'],
                            'Date': order['order_date'],
                            'Customer': order['customer_name'],
                            'Product': order['product_title'][:60] + '...' if len(order['product_title']) > 60 else
                            order['product_title'],
                            'Status': order['delivery_status'],
                            'Total': order['order_total']
                        }
                        for order in analysis['missing_orders']
                    ])

                    st.dataframe(missing_df, use_container_width=True)

                # Duplicate matches (1 Amazon → multiple eBay)
                if analysis['duplicate_orders']:
                    st.markdown("**⚠️ Amazon Orders Matched Multiple Times:**")

                    for dup in analysis['duplicate_orders']:
                        st.warning(f"**{dup['amazon_order_id']}** matched with **{dup['count']} eBay orders**")

                        for match in dup['ebay_matches']:
                            buyer = match.get('ebay_buyer_name', 'N/A')
                            profit = match.get('calculated_profit_usd', 0)
                            ebay_order = match.get('ebay_order_number', 'N/A')
                            st.write(f"  → eBay: {ebay_order} | Buyer: {buyer} | Profit: ${profit:.2f}")

                # Download account-specific data
                st.markdown("**📄 Download Account Data:**")

                account_data = {
                    'account_name': account_name,
                    'analysis_date': datetime.now().isoformat(),
                    'simulation_method': 'independent_matching',
                    'performance_metrics': {
                        'available_ebay_orders': int(analysis['available_ebay_orders']),
                        'amazon_orders': int(analysis['amazon_orders']),
                        'actual_matches': int(analysis['actual_matches']),
                        'theoretical_max': int(analysis['theoretical_max']),
                        'efficiency_percentage': float(analysis['efficiency']),
                        'missing_count': int(analysis['missing_count']),
                        'duplicate_count': int(analysis['duplicate_count'])
                    },
                    'missing_orders': analysis['missing_orders'],
                    'duplicate_orders': analysis['duplicate_orders']
                }

                import json
                account_json = json.dumps(account_data, indent=2, default=str)

                st.download_button(
                    f"📄 Download {account_name} Independent Analysis",
                    data=account_json,
                    file_name=f"independent_analysis_{account_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json",
                    key=f"download_independent_{account_name}_{datetime.now().strftime('%H%M%S')}"
                )

        # Overall insights
        st.markdown("##### 🎯 Overall Insights")

        total_missing = sum(summary['missing_count'] for summary in account_summaries)
        total_duplicates = sum(summary['duplicate_count'] for summary in account_summaries)
        avg_efficiency = sum(summary['efficiency'] for summary in account_summaries) / len(account_summaries)

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Total Missing Orders", total_missing)

        with col2:
            st.metric("Total Duplicate Matches", total_duplicates)

        with col3:
            problematic_accounts = sum(1 for summary in account_summaries if summary['has_issues'])
            st.metric("Accounts with Issues", problematic_accounts)

        # Recommendations
        with st.expander("💡 Optimization Recommendations"):
            st.markdown("""
            **Based on Independent Account Analysis:**

            **For Low Efficiency Accounts:**
            - Review matching thresholds specifically for underperforming accounts
            - Check for account-specific patterns (product types, customer regions, etc.)
            - Consider account-specific matching rules

            **For Missing Orders:**
            - Verify delivery statuses (returns, cancellations)
            - Check date ranges and timing
            - Look for address format differences
            - Consider international shipping patterns

            **For Duplicate Matches:**
            - May indicate legitimate business cases (bulk orders, family orders)
            - Consider quantity-based matching rules
            - Review customer patterns (same buyer, multiple orders)

            **Account-Specific Strategies:**
            - High-performing accounts: Maintain current settings
            - Low-performing accounts: Adjust thresholds or add custom rules
            - Consider account grouping by performance characteristics
            """)

    def simulate_independent_matching(self, account_name: str,
                                      ebay_orders_available: pd.DataFrame,
                                      amazon_orders_this_account: pd.DataFrame,
                                      actual_matches_this_account: pd.DataFrame) -> Dict:
        """
        Simulate how this account would perform if matched independently
        """
        # Available resources for this account
        available_ebay_count = len(ebay_orders_available)
        amazon_orders_count = len(amazon_orders_this_account)
        actual_matches_count = len(actual_matches_this_account)

        # Theoretical maximum matches (limited by smaller dataset)
        theoretical_max = min(available_ebay_count, amazon_orders_count)

        # Calculate efficiency
        efficiency = (actual_matches_count / amazon_orders_count * 100) if amazon_orders_count > 0 else 0

        # Find missing Amazon orders (didn't match any eBay)
        amazon_order_ids = self.extract_order_ids_from_original_amazon(amazon_orders_this_account)
        matched_amazon_ids = self.extract_order_ids_from_matched_account(actual_matches_this_account)
        missing_amazon_ids = set(amazon_order_ids) - set(matched_amazon_ids)

        # Find duplicates (1 Amazon matched multiple eBay)
        matched_series = pd.Series(matched_amazon_ids)
        duplicate_amazon_ids = matched_series[matched_series.duplicated()].unique()

        # Get missing order details
        missing_orders = []
        for missing_id in missing_amazon_ids:
            missing_order = amazon_orders_this_account[
                amazon_orders_this_account['orderId'] == missing_id
                ]
            if not missing_order.empty:
                order_data = missing_order.iloc[0].to_dict()
                missing_orders.append({
                    'order_id': missing_id,
                    'order_date': order_data.get('orderDate', 'N/A'),
                    'order_total': order_data.get('orderTotal', 'N/A'),
                    'delivery_status': order_data.get('deliveryStatus', 'N/A'),
                    'customer_name': self._extract_customer_name_from_amazon(order_data),
                    'product_title': self._extract_product_title_from_amazon(order_data)
                })

        # Get duplicate order details
        duplicate_orders = []
        for dup_id in duplicate_amazon_ids:
            count = matched_series.value_counts()[dup_id]
            duplicate_matches = actual_matches_this_account[
                actual_matches_this_account['amazon_orderid'] == dup_id
                ]

            duplicate_orders.append({
                'amazon_order_id': dup_id,
                'count': count,
                'ebay_matches': duplicate_matches.to_dict('records') if not duplicate_matches.empty else []
            })

        return {
            'account_name': account_name,
            'available_ebay_orders': available_ebay_count,
            'amazon_orders': amazon_orders_count,
            'actual_matches': actual_matches_count,
            'theoretical_max': theoretical_max,
            'efficiency': efficiency,
            'missing_count': len(missing_amazon_ids),
            'duplicate_count': len(duplicate_amazon_ids),
            'unmatched_potential': max(0, theoretical_max - actual_matches_count),
            'missing_orders': missing_orders,
            'duplicate_orders': duplicate_orders,
            'has_issues': len(missing_amazon_ids) > 0 or len(duplicate_amazon_ids) > 0 or efficiency < 95
        }

    def extract_account_from_filename(self, filename: str) -> str:
        """Extract account name from filename"""
        if not filename:
            return "unknown"

        # Remove extension
        name_without_ext = filename.rsplit('.', 1)[0]

        # Split by underscore and take first part
        parts = name_without_ext.split('_')
        if len(parts) > 1:
            return parts[0]  # "buyer1_amazon.json" -> "buyer1"

        # If no underscore, take first word
        first_word = name_without_ext.split()[0] if name_without_ext.split() else name_without_ext
        return first_word

    def get_account_debug_statistics(self, original_amazon_df: pd.DataFrame,
                                     matched_results: pd.DataFrame) -> Dict:
        """
        Get comprehensive account-separated debug statistics
        """
        if 'amazon_account' not in original_amazon_df.columns or 'amazon_account' not in matched_results.columns:
            return {}

        all_accounts = sorted(set(original_amazon_df['amazon_account'].unique()).union(
            set(matched_results['amazon_account'].unique())
        ))

        account_stats = {}

        for account in all_accounts:
            original_account_df = original_amazon_df[original_amazon_df['amazon_account'] == account]
            matched_account_df = matched_results[matched_results['amazon_account'] == account]

            analysis = self.analyze_account_separately(account, original_account_df, matched_account_df)
            account_stats[account] = analysis

        return {
            'total_accounts': len(all_accounts),
            'account_statistics': account_stats,
            'overall_missing': sum(stats['missing_count'] for stats in account_stats.values()),
            'overall_duplicates': sum(stats['duplicate_count'] for stats in account_stats.values()),
            'problematic_accounts': sum(1 for stats in account_stats.values() if stats['has_issues'])
        }