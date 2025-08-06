# utils/debug_analyzer.py - COMPLETE VERSION with Unmatched eBay Analysis
"""
Account-Separated Matching Debug Analyzer Module
Analyzes each Amazon account separately to avoid cross-account confusion
Enhanced with unmatched eBay orders analysis
"""

import pandas as pd
import streamlit as st
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import json


class AccountSeparatedDebugAnalyzer:
    """
    Account-separated debug analyzer for order matching process
    Analyzes each Amazon account independently + unmatched eBay orders
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

    def analyze_unmatched_ebay_orders(self, original_ebay_files_data: List,
                                      matched_results: pd.DataFrame) -> Dict:
        """
        NEW: Analyze which eBay orders are not matched with any Amazon order
        """
        if matched_results.empty:
            return {}

        # Get all matched eBay order numbers
        matched_ebay_orders = set()
        possible_fields = ['ebay_order_number', 'ebay_order_id', 'ebay_orderid']

        for field in possible_fields:
            if field in matched_results.columns:
                matched_orders = matched_results[field].dropna().tolist()
                matched_ebay_orders.update(matched_orders)
                break

        # Analyze each eBay file
        unmatched_analysis = {}
        total_unmatched = 0

        for filename, ebay_df in original_ebay_files_data:
            # Extract eBay order numbers from this file
            file_ebay_orders = self.extract_ebay_order_numbers(ebay_df)

            # Find unmatched orders in this file
            unmatched_in_file = []
            for order_num in file_ebay_orders:
                if order_num not in matched_ebay_orders:
                    # Get order details
                    order_row = ebay_df[ebay_df['Order number'] == order_num]
                    if not order_row.empty:
                        order_data = order_row.iloc[0].to_dict()
                        unmatched_in_file.append({
                            'order_number': order_num,
                            'buyer_name': order_data.get('Buyer name', 'N/A'),
                            'item_title': order_data.get('Item title', 'N/A')[:60] + '...',
                            'order_date': order_data.get('Order creation date', 'N/A'),
                            'earnings': order_data.get('Order earnings', 'N/A'),
                            'country': order_data.get('Ship to country', 'N/A'),
                            'raw_data': order_data
                        })

            unmatched_analysis[filename] = {
                'total_orders': len(file_ebay_orders),
                'unmatched_count': len(unmatched_in_file),
                'unmatched_orders': unmatched_in_file,
                'match_rate': ((len(file_ebay_orders) - len(unmatched_in_file)) / len(file_ebay_orders) * 100) if len(
                    file_ebay_orders) > 0 else 0
            }

            total_unmatched += len(unmatched_in_file)

        return {
            'total_unmatched_ebay': total_unmatched,
            'file_breakdown': unmatched_analysis,
            'total_files': len(original_ebay_files_data)
        }

    def extract_ebay_order_numbers(self, ebay_df: pd.DataFrame) -> List[str]:
        """Extract eBay order numbers from DataFrame"""
        possible_fields = ['Order number', 'order_number', 'orderNumber', 'order_id']

        for field in possible_fields:
            if field in ebay_df.columns:
                return ebay_df[field].dropna().astype(str).tolist()

        return []

    def show_isolated_account_analysis(self, original_amazon_files_data: List,
                                       original_ebay_files_data: List,
                                       matched_results: pd.DataFrame):
        """
        ENHANCED: Analyze each Amazon account + unmatched eBay orders
        """
        if matched_results.empty:
            st.warning("⚠️ No matched results to analyze")
            return

        # Check if account field exists
        if 'amazon_account' not in matched_results.columns:
            st.error("❌ No amazon_account field found in matched results")
            return

        st.markdown("#### 🔍 Isolated Account Analysis")
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

        # 🆕 NEW: Unmatched eBay Orders Analysis
        st.markdown("##### 📋 Unmatched eBay Orders Analysis")

        unmatched_analysis = self.analyze_unmatched_ebay_orders(original_ebay_files_data, matched_results)

        if unmatched_analysis:
            # Unmatched summary
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Unmatched eBay", unmatched_analysis['total_unmatched_ebay'])
            with col2:
                total_ebay = sum(data['total_orders'] for data in unmatched_analysis['file_breakdown'].values())
                match_rate = ((total_ebay - unmatched_analysis[
                    'total_unmatched_ebay']) / total_ebay * 100) if total_ebay > 0 else 0
                st.metric("Overall eBay Match Rate", f"{match_rate:.1f}%")
            with col3:
                st.metric("eBay Files Analyzed", unmatched_analysis['total_files'])

            # File-by-file breakdown
            st.markdown("**📁 Unmatched eBay Orders by File:**")

            for filename, file_data in unmatched_analysis['file_breakdown'].items():
                if file_data['unmatched_count'] > 0:
                    status_icon = "❌" if file_data['match_rate'] < 90 else "⚠️" if file_data['match_rate'] < 95 else "✅"

                    with st.expander(
                            f"{status_icon} **{filename}** - {file_data['unmatched_count']} unmatched ({file_data['match_rate']:.1f}% match rate)"):

                        # File statistics
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Total eBay Orders", file_data['total_orders'])
                        with col2:
                            st.metric("Unmatched Orders", file_data['unmatched_count'])
                        with col3:
                            st.metric("Match Rate", f"{file_data['match_rate']:.1f}%")

                        # Unmatched orders table
                        if file_data['unmatched_orders']:
                            st.markdown("**🔍 Unmatched eBay Orders:**")

                            unmatched_df = pd.DataFrame([
                                {
                                    'eBay Order': order['order_number'],
                                    'Buyer': order['buyer_name'][:25] + (
                                        '...' if len(order['buyer_name']) > 25 else ''),
                                    'Product': order['item_title'][:40] + (
                                        '...' if len(order['item_title']) > 40 else ''),
                                    'Date': order['order_date'],
                                    'Earnings': order['earnings'],
                                    'Country': order['country']
                                }
                                for order in file_data['unmatched_orders'][:10]  # Show first 10
                            ])

                            st.dataframe(unmatched_df, use_container_width=True, hide_index=True)

                            if len(file_data['unmatched_orders']) > 10:
                                st.info(f"📋 Showing first 10 of {len(file_data['unmatched_orders'])} unmatched orders")

                        # Download unmatched orders for this file
                        unmatched_data = {
                            'filename': filename,
                            'analysis_date': datetime.now().isoformat(),
                            'file_statistics': {
                                'total_orders': file_data['total_orders'],
                                'unmatched_count': file_data['unmatched_count'],
                                'match_rate_percentage': file_data['match_rate']
                            },
                            'unmatched_orders': file_data['unmatched_orders']
                        }

                        unmatched_json = json.dumps(unmatched_data, indent=2, default=str)

                        st.download_button(
                            f"📄 Download Unmatched Orders - {filename}",
                            data=unmatched_json,
                            file_name=f"unmatched_ebay_{filename.replace('.json', '')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                            mime="application/json",
                            key=f"download_unmatched_{filename}_{datetime.now().strftime('%H%M%S')}"
                        )

                else:
                    st.success(f"✅ **{filename}** - All orders matched (100% match rate)")

        # Analyze each account independently
        st.markdown("##### 🔍 Independent Amazon Account Analysis")

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

        total_missing_amazon = sum(summary['missing_count'] for summary in account_summaries)
        total_duplicates = sum(summary['duplicate_count'] for summary in account_summaries)
        total_unmatched_ebay = unmatched_analysis.get('total_unmatched_ebay', 0)

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Missing Amazon Orders", total_missing_amazon)

        with col2:
            st.metric("Duplicate Amazon Matches", total_duplicates)

        with col3:
            st.metric("Unmatched eBay Orders", total_unmatched_ebay)

        # Enhanced recommendations
        with st.expander("💡 Enhanced Optimization Recommendations"):
            st.markdown("""
            **Based on Complete Order Analysis:**

            **For Unmatched eBay Orders:**
            - Check if these are cancelled/refunded orders
            - Verify customer names and addresses match Amazon format
            - Look for international orders that may need eIS CO detection
            - Consider date range mismatches between eBay and Amazon

            **For Missing Amazon Orders:**
            - Verify delivery statuses (returns, cancellations)
            - Check for address format differences
            - Look for account-specific patterns

            **For Duplicate Matches:**
            - May indicate legitimate business cases (bulk orders, family orders)
            - Consider quantity-based matching rules
            - Review customer patterns

            **File-Specific Issues:**
            - Files with low match rates may have data quality issues
            - Check date formats and field mappings
            - Verify account extraction from filenames
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