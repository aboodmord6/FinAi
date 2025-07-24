from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import tool
from langchain.memory import ConversationBufferMemory
from langchain.schema import HumanMessage, AIMessage
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv
import os
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Any, Optional
from datetime import datetime
from django.db.models import Q
from django.utils import timezone
import uuid

# Import Django models
from ..models import (
    FinancialInstitution,
    FXRate,
    Accounts,
    FinancialProduct,
    ChatMemory,
)
from django.contrib.auth import get_user_model

User = get_user_model()

load_dotenv()


class DjangoChatMemory:
    """Custom memory implementation using Django models."""

    def __init__(self, user_id: int, session_id: Optional[str] = None):
        self.user_id = user_id
        self.session_id = session_id or str(uuid.uuid4())
        self.memory_key = "chat_history"
        self.return_messages = True

    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, str]) -> None:
        """Save user input and assistant output to database."""
        try:
            # Save user message
            ChatMemory.objects.create(
                user_id=self.user_id,
                message_type="user",
                content=inputs.get("input", ""),
                session_id=self.session_id,
            )

            # Save assistant message
            ChatMemory.objects.create(
                user_id=self.user_id,
                message_type="assistant",
                content=outputs.get("output", ""),
                session_id=self.session_id,
            )
        except Exception as e:
            print(f"Error saving chat memory: {e}")

    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Load conversation history from database."""
        try:
            # Get recent messages for this user and session
            messages = ChatMemory.objects.filter(
                user_id=self.user_id, session_id=self.session_id
            ).order_by("-timestamp")[
                :5
            ]  # Last 20 messages, ordered by most recent first

            # Reverse to get chronological order (oldest to newest)
            messages = list(messages)[::-1]

            chat_history = []
            for msg in messages:
                if msg.message_type == "user":
                    chat_history.append(HumanMessage(content=msg.content))
                elif msg.message_type == "assistant":
                    chat_history.append(AIMessage(content=msg.content))

            return {self.memory_key: chat_history}
        except Exception as e:
            print(f"Error loading chat memory: {e}")
            return {self.memory_key: []}

    def clear(self) -> None:
        """Clear conversation history for this session."""
        try:
            ChatMemory.objects.filter(
                user_id=self.user_id, session_id=self.session_id
            ).delete()
        except Exception as e:
            print(f"Error clearing chat memory: {e}")


# ==================== FINTECH TOOLS ====================


@tool
def get_user_profile(user_id: int) -> str:
    """Get user's personal profile information."""
    try:
        user = User.objects.get(id=user_id)  # type: ignore
        result = f"👤 User Profile:\n"
        result += f"Name: {user.first_name} {user.last_name}\n"
        result += f"Username: {user.username}\n"
        result += f"Email: {user.email}\n"
        result += f"Account Status: {'Active' if user.is_active else 'Inactive'}\n"

        account_count = Accounts.objects.filter(user=user).count()  # type: ignore
        result += f"Connected Accounts: {account_count}\n"

        banks = (
            Accounts.objects.filter(user=user)  # type: ignore
            .values_list("financial_institution__name", flat=True)
            .distinct()
        )
        if banks:
            result += f"Banking Partners: {', '.join(banks)}\n"

        return result
    except User.DoesNotExist:
        return "User not found"
    except Exception as e:
        return f"Error retrieving user profile: {str(e)}"


@tool
def get_user_financial_overview(user_id: int) -> str:
    """Get comprehensive financial overview for the user."""
    try:
        user = User.objects.get(id=user_id)  # type: ignore
        accounts = Accounts.objects.filter(user=user).select_related("financial_institution")  # type: ignore

        result = f"📊 Financial Overview for {user.first_name}:\n\n"

        total_accounts = accounts.count()
        active_accounts = accounts.filter(account_status="ACTIVE").count()
        accounts_with_balance = accounts.filter(available_balance__isnull=False).count()

        result += f"📈 Account Summary:\n"
        result += f"• Total Accounts: {total_accounts}\n"
        result += f"• Active Accounts: {active_accounts}\n"
        result += f"• Accounts with Balance: {accounts_with_balance}\n\n"

        unique_banks = accounts.values_list(
            "financial_institution__name", flat=True
        ).distinct()
        result += f"🏦 Banking Relationships:\n"
        result += f"• Connected Banks: {len(unique_banks)}\n"
        if unique_banks:
            result += f"• Banks: {', '.join(unique_banks)}\n\n"

        currencies = accounts.values_list("account_currency", flat=True).distinct()
        result += f"💱 Currency Portfolio:\n"
        result += f"• Currencies: {len(currencies)}\n"
        if currencies:
            result += f"• Types: {', '.join(currencies)}\n\n"

        total_balance_accounts = accounts.filter(available_balance__isnull=False)
        if total_balance_accounts.exists():
            balance_by_currency = {}
            for account in total_balance_accounts:
                currency = account.account_currency
                if currency not in balance_by_currency:
                    balance_by_currency[currency] = Decimal("0")
                balance_by_currency[currency] += account.available_balance

            result += f"💰 Balance Portfolio:\n"
            for currency, total in balance_by_currency.items():
                result += f"• {currency}: {total}\n"

        return result
    except User.DoesNotExist:
        return "User not found"
    except Exception as e:
        return f"Error retrieving financial overview: {str(e)}"


@tool
def get_user_account_summary(user_id: int) -> str:
    """Get personalized account summary with recommendations."""
    try:
        user = User.objects.get(id=user_id)  # type: ignore
        accounts = Accounts.objects.filter(user=user).select_related("financial_institution")  # type: ignore

        result = f"📋 Account Summary for {user.first_name}:\n\n"

        if not accounts.exists():
            result += "No accounts connected yet. Consider linking your bank accounts for better financial management.\n"
            return result

        bank_accounts = {}
        for account in accounts:
            bank_name = account.financial_institution.name
            if bank_name not in bank_accounts:
                bank_accounts[bank_name] = []
            bank_accounts[bank_name].append(account)

        for bank_name, bank_account_list in bank_accounts.items():
            result += f"🏦 {bank_name}:\n"
            for account in bank_account_list:
                result += f"   • Account: {account.account_id}\n"
                result += f"     Currency: {account.account_currency}\n"
                result += f"     Status: {account.account_status}\n"
                if account.available_balance:
                    result += f"     Balance: {account.available_balance} {account.account_currency}\n"
                else:
                    result += f"     Balance: Not available\n"
            result += f"\n"

        result += f"💡 Personalized Insights:\n"
        if len(bank_accounts) == 1:
            result += "• Consider diversifying across multiple banks for better rates\n"
        elif len(bank_accounts) > 3:
            result += (
                "• You have accounts across multiple banks - great diversification!\n"
            )

        currencies = accounts.values_list("account_currency", flat=True).distinct()
        if len(currencies) > 1:
            result += f"• Multi-currency portfolio detected - use our converter for better rates\n"

        inactive_accounts = accounts.filter(account_status="INACTIVE").count()
        if inactive_accounts > 0:
            result += f"• You have {inactive_accounts} inactive account(s) - consider reactivating\n"

        return result
    except User.DoesNotExist:
        return "User not found"
    except Exception as e:
        return f"Error retrieving account summary: {str(e)}"


@tool
def get_fx_rate(
    source_currency: str, target_currency: str, bank_name: Optional[str] = None
) -> str:
    """Get foreign exchange rate between two currencies."""
    try:
        query = FXRate.objects.filter(
            source_currency=source_currency.upper(),
            target_currency=target_currency.upper(),
        )

        if bank_name:
            query = query.filter(FinancialInstitution__name__icontains=bank_name)

        rates = query.select_related("FinancialInstitution").order_by(
            "-effective_date"
        )[:5]

        if not rates:
            return f"No rates found for {source_currency}/{target_currency}"

        rate_list = []
        for rate in rates:
            rate_list.append(
                f"{rate.FinancialInstitution.name}: {rate.conversion_value}"
            )

        return f"{source_currency}/{target_currency} rates: {', '.join(rate_list)}"
    except Exception as e:
        return f"Error: {str(e)}"


@tool
def compare_fx_rates(source_currency: str, target_currency: str) -> str:
    """Compare foreign exchange rates across all available banks."""
    try:
        rates = (
            FXRate.objects.filter(  # type: ignore
                source_currency=source_currency.upper(),
                target_currency=target_currency.upper(),
            )
            .select_related("FinancialInstitution")
            .order_by("-effective_date")
        )

        if not rates:
            return f"No rates available for {source_currency}/{target_currency}"

        latest_rates = {}
        for rate in rates:
            bank_name = rate.FinancialInstitution.name
            if bank_name not in latest_rates:
                latest_rates[bank_name] = rate

        sorted_rates = sorted(
            latest_rates.items(), key=lambda x: x[1].conversion_value, reverse=True
        )

        result = f"Best {source_currency}/{target_currency} rates:\n"
        for i, (bank_name, rate) in enumerate(sorted_rates[:5], 1):
            result += f"{i}. {bank_name}: {rate.conversion_value}\n"

        rates_values = [rate.conversion_value for _, rate in sorted_rates]
        if rates_values:
            avg_rate = sum(rates_values) / len(rates_values)
            result += f"\nAverage rate: {avg_rate:.4f}"
            result += f"\nBest rate: {max(rates_values):.4f}"
            result += f"\nWorst rate: {min(rates_values):.4f}"

        return result
    except Exception as e:
        return f"Error comparing rates: {str(e)}"


@tool
def convert_currency(
    amount: float,
    source_currency: str,
    target_currency: str,
    bank_name: Optional[str] = None,
) -> str:
    """Convert currency amount using current exchange rates."""
    try:
        if amount <= 0:
            return "Please provide a positive amount to convert"

        query = FXRate.objects.filter(  # type: ignore
            source_currency=source_currency.upper(),
            target_currency=target_currency.upper(),
        )

        if bank_name:
            query = query.filter(FinancialInstitution__name__icontains=bank_name)

        rate = (
            query.select_related("FinancialInstitution")
            .order_by("-effective_date")
            .first()
        )

        if not rate:
            return f"No exchange rate found for {source_currency}/{target_currency}"

        converted_amount = Decimal(str(amount)) * rate.conversion_value
        converted_amount = converted_amount.quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        result = f"Conversion Result:\n"
        result += f"{amount} {source_currency} = {converted_amount} {target_currency}\n"
        result += f"Rate: {rate.conversion_value} ({rate.FinancialInstitution.name})\n"
        result += f"Last updated: {rate.effective_date.strftime('%Y-%m-%d %H:%M')}"

        return result
    except Exception as e:
        return f"Error converting currency: {str(e)}"


@tool
def get_bank_info(bank_name: str) -> str:
    """Get information about a specific bank."""
    try:
        banks = FinancialInstitution.objects.filter(name__icontains=bank_name)  # type: ignore

        if not banks:
            return f"No bank found with name containing '{bank_name}'"

        result = f"Bank Information:\n"
        for bank in banks[:3]:
            result += f"\n--- {bank.name} ---\n"
            if bank.website_url:
                result += f"Website: {bank.website_url}\n"
            if bank.contact_email:
                result += f"Email: {bank.contact_email}\n"
            if bank.contact_phone:
                result += f"Phone: {bank.contact_phone}\n"
            if bank.BIC_code:
                result += f"BIC Code: {bank.BIC_code}\n"
            if bank.address:
                result += f"Address: {bank.address}\n"

        return result
    except Exception as e:
        return f"Error retrieving bank information: {str(e)}"


@tool
def get_available_currencies() -> str:
    """Get list of all available currencies in the system."""
    try:
        source_currencies = set(FXRate.objects.values_list("source_currency", flat=True))  # type: ignore
        target_currencies = set(FXRate.objects.values_list("target_currency", flat=True))  # type: ignore
        all_currencies = sorted(source_currencies.union(target_currencies))

        result = f"Available currencies ({len(all_currencies)}):\n"
        result += ", ".join(all_currencies)

        return result
    except Exception as e:
        return f"Error retrieving currencies: {str(e)}"


@tool
def get_popular_currency_pairs() -> str:
    """Get popular currency pairs with their current rates."""
    try:
        popular_pairs = [
            ("USD", "EUR"),
            ("USD", "GBP"),
            ("EUR", "GBP"),
            ("USD", "JPY"),
            ("USD", "JOD"),
            ("EUR", "JOD"),
        ]

        result = "Popular Currency Pairs:\n"
        for source, target in popular_pairs:
            rate = (
                FXRate.objects.filter(source_currency=source, target_currency=target)  # type: ignore
                .select_related("FinancialInstitution")
                .order_by("-effective_date")
                .first()
            )

            if rate:
                result += f"{source}/{target}: {rate.conversion_value} ({rate.FinancialInstitution.name})\n"

        return result
    except Exception as e:
        return f"Error retrieving popular currency pairs: {str(e)}"


@tool
def get_user_accounts(user_id: int) -> str:
    """Get user's bank accounts information."""
    try:
        accounts = Accounts.objects.filter(user_id=user_id).select_related("financial_institution")  # type: ignore

        if not accounts:
            return "No accounts found for this user"

        result = f"User Accounts ({accounts.count()}):\n"
        for account in accounts:
            result += f"\n--- {account.financial_institution.name} ---\n"
            result += f"Account ID: {account.account_id}\n"
            result += f"Currency: {account.account_currency}\n"
            if account.available_balance:
                result += (
                    f"Balance: {account.available_balance} {account.account_currency}\n"
                )
            result += f"Status: {account.account_status}\n"

        return result
    except Exception as e:
        return f"Error retrieving user accounts: {str(e)}"


@tool
def get_user_balance(user_id: int, account_id: Optional[str] = None) -> str:
    """Get user's account balance for a specific account or all accounts."""
    try:
        query = Accounts.objects.filter(user_id=user_id).select_related(
            "financial_institution"
        )

        if account_id:
            query = query.filter(account_id=account_id)

        accounts = query.all()

        if not accounts:
            return "No accounts found"

        balances = []
        for account in accounts:
            balance_info = {
                "bank": account.financial_institution.name,
                "account_id": account.account_id,
                "balance": (
                    str(account.available_balance)
                    if account.available_balance
                    else "Not available"
                ),
                "currency": account.account_currency,
                "status": account.account_status,
            }
            balances.append(
                f"Bank: {balance_info['bank']}, Account: {balance_info['account_id']}, Balance: {balance_info['balance']} {balance_info['currency']}, Status: {balance_info['status']}"
            )

        return "User account balances: " + "; ".join(balances)
    except Exception as e:
        return f"Error: {str(e)}"


@tool
def get_total_balance(user_id: int) -> str:
    """Get total balance across all user accounts, grouped by currency."""
    try:
        accounts = Accounts.objects.filter(
            user_id=user_id, available_balance__isnull=False
        ).select_related("financial_institution")

        if not accounts:
            return "No accounts with balance data found"

        currency_totals = {}
        for account in accounts:
            currency = account.account_currency
            if currency not in currency_totals:
                currency_totals[currency] = Decimal("0")
            currency_totals[currency] += account.available_balance

        totals = [f"{currency}: {total}" for currency, total in currency_totals.items()]
        return f"Total balances by currency: {', '.join(totals)}"
    except Exception as e:
        return f"Error: {str(e)}"


@tool
def get_balance_summary(user_id: int) -> str:
    """Get a comprehensive balance summary with insights."""
    try:
        accounts = Accounts.objects.filter(user_id=user_id).select_related("financial_institution")  # type: ignore

        if not accounts:
            return "No accounts found for this user"

        total_accounts = accounts.count()
        active_accounts = accounts.filter(account_status="ACTIVE").count()
        accounts_with_balance = accounts.filter(available_balance__isnull=False).count()

        result = f"📊 Balance Summary Report:\n"
        result += f"Total Accounts: {total_accounts}\n"
        result += f"Active Accounts: {active_accounts}\n"
        result += f"Accounts with Balance Data: {accounts_with_balance}\n\n"

        currency_data = {}
        for account in accounts:
            if account.available_balance:
                currency = account.account_currency
                if currency not in currency_data:
                    currency_data[currency] = {
                        "total": Decimal("0"),
                        "count": 0,
                        "banks": set(),
                    }

                currency_data[currency]["total"] += account.available_balance
                currency_data[currency]["count"] += 1
                currency_data[currency]["banks"].add(account.financial_institution.name)

        if currency_data:
            result += "💱 Balance by Currency:\n"
            for currency, data in currency_data.items():
                result += (
                    f"• {currency}: {data['total']} across {data['count']} account(s)\n"
                )
                result += f"  Banks: {', '.join(data['banks'])}\n"

        result += f"\n📋 Account Status:\n"
        status_counts = {}
        for account in accounts:
            status = account.account_status or "Unknown"
            status_counts[status] = status_counts.get(status, 0) + 1

        for status, count in status_counts.items():
            result += f"• {status}: {count} account(s)\n"

        return result
    except Exception as e:
        return f"Error generating balance summary: {str(e)}"


@tool
def check_account_balance(user_id: int, bank_name: str) -> str:
    """Check balance for accounts at a specific bank."""
    try:
        accounts = Accounts.objects.filter(  # type: ignore
            user_id=user_id, financial_institution__name__icontains=bank_name
        ).select_related("financial_institution")

        if not accounts:
            return f"No accounts found at {bank_name}"

        result = f"💰 Balance at {bank_name}:\n"
        total_balance_by_currency = {}

        for account in accounts:
            result += f"\n📱 Account: {account.account_id}\n"
            result += f"   Currency: {account.account_currency}\n"

            if account.available_balance:
                result += f"   Balance: {account.available_balance} {account.account_currency}\n"
                currency = account.account_currency
                if currency not in total_balance_by_currency:
                    total_balance_by_currency[currency] = Decimal("0")
                total_balance_by_currency[currency] += account.available_balance
            else:
                result += f"   Balance: Not available\n"

            result += f"   Status: {account.account_status}\n"

        if total_balance_by_currency:
            result += f"\n📊 Total at {bank_name}:\n"
            for currency, total in total_balance_by_currency.items():
                result += f"   {currency}: {total}\n"

        return result
    except Exception as e:
        return f"Error checking account balance: {str(e)}"


@tool
def get_all_banks_info() -> str:
    """Get information about all available banks."""
    try:
        banks = FinancialInstitution.objects.all().select_related("address")
        if not banks:
            return "No banks found in the system."

        result = "🏦 Available Banks:\n\n"
        for bank in banks:
            result += f"📌 {bank.name}\n"
            if bank.website_url:
                result += f"   Website: {bank.website_url}\n"
            if bank.contact_email:
                result += f"   Email: {bank.contact_email}\n"
            if bank.contact_phone:
                result += f"   Phone: {bank.contact_phone}\n"
            if bank.BIC_code:
                result += f"   BIC Code: {bank.BIC_code}\n"
            if bank.address:
                result += f"   Address: {bank.address}\n"
            result += "\n"
        return result
    except Exception as e:
        return f"Error retrieving all banks information: {str(e)}"


@tool
def get_user_connected_bank_products(user_id: int) -> str:
    """Get products from banks where the user has connected accounts."""
    try:
        user = User.objects.get(id=user_id)  # type: ignore

        # Get user's connected banks
        user_accounts = Accounts.objects.filter(user=user).select_related(
            "financial_institution"
        )
        user_banks = user_accounts.values_list(
            "financial_institution", flat=True
        ).distinct()

        if not user_banks:
            return "You don't have any connected bank accounts yet. Connect your accounts to see available products."

        result = f"🏦 Products from your connected banks:\n\n"

        for bank_id in user_banks:
            bank = FinancialInstitution.objects.get(id=bank_id)
            products = FinancialProduct.objects.filter(
                FinancialInstitution=bank
            ).select_related("category")

            if not products.exists():
                result += f"📌 {bank.name}\n"
                result += f"   No products available\n\n"
                continue

            result += f"📌 {bank.name} • Offers and Services:\n"

            # Group products by category
            categories = {}
            for product in products:
                category_name = product.category.name if product.category else "Other"
                if category_name not in categories:
                    categories[category_name] = []
                categories[category_name].append(product)

            for category_name, category_products in categories.items():
                result += f"   📂 {category_name}:\n"
                for product in category_products:
                    result += f"      • {product.commercial_name}"
                    if product.type:
                        result += f" ({product.type})"
                    if product.description:
                        result += f" - {product.description[:60]}"
                        if len(product.description) > 60:
                            result += "..."
                    result += "\n"

            result += "\n"

        # Add personalized recommendations
        result += "💡 Personalized Insights:\n"
        bank_count = len(user_banks)
        if bank_count == 1:
            result += (
                "• Consider exploring products from other banks for better rates\n"
            )
        elif bank_count > 1:
            result += f"• You have accounts with {bank_count} banks - great for comparing products!\n"

        # Check if user has products from their banks
        total_products = FinancialProduct.objects.filter(
            FinancialInstitution__in=user_banks
        ).count()
        if total_products > 0:
            result += f"• {total_products} products available from your banks\n"

        return result
    except User.DoesNotExist:
        return "User not found"
    except Exception as e:
        return f"Error retrieving user's bank products: {str(e)}"


# ==================== LANGCHAIN SETUP ====================


def get_fintech_agent():
    """Initialize the LLM agent."""
    try:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is not set")

        return ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0.75,
            api_key=api_key,
        )
    except Exception as e:
        raise e


def get_personalized_greeting(user_id: int) -> str:
    """Generate a personalized greeting for the user."""
    try:
        user = User.objects.get(id=user_id)
        accounts = Accounts.objects.filter(user=user)

        current_hour = datetime.now().hour
        if current_hour < 12:
            time_greeting = "Good morning"
        elif current_hour < 17:
            time_greeting = "Good afternoon"
        else:
            time_greeting = "Good evening"

        name = user.first_name if user.first_name else user.username
        greeting = f"{time_greeting}, {name}! 👋\n\n"

        account_count = accounts.count()
        if account_count == 0:
            greeting += "Welcome to MCS! I'm here to help you get started with connecting your bank accounts and managing your finances.\n\n"
        elif account_count == 1:
            bank_name = accounts.first().financial_institution.name
            greeting += f"I see you have an account with {bank_name}. I can help you check balances, compare rates, and more!\n\n"
        else:
            banks = accounts.values_list(
                "financial_institution__name", flat=True
            ).distinct()
            greeting += f"Great to see you managing accounts across {len(banks)} banks! I can help you with balances, conversions, and comparisons.\n\n"

        greeting += "What would you like to know about your finances today?"
        return greeting
    except Exception:
        return "Hello! I'm your AI financial assistant. How can I help you today?"


def is_greeting_message(prompt: str) -> bool:
    """Check if the prompt is a greeting message."""
    greeting_words = [
        "hello",
        "hi",
        "hey",
        "good morning",
        "good afternoon",
        "good evening",
    ]
    prompt_lower = prompt.lower().strip()

    return (
        any(prompt_lower.startswith(word) for word in greeting_words)
        or any(word == prompt_lower for word in greeting_words)
        or (
            len(prompt.split()) <= 3
            and any(word in prompt_lower for word in greeting_words)
        )
    )


def run_fintech_agent(
    prompt: str, user_id: Optional[int] = None, session_id: Optional[str] = None
) -> str:
    """Run the fintech agent with optional user context and memory."""
    try:
        # Handle greetings directly
        if user_id and is_greeting_message(prompt):
            return get_personalized_greeting(user_id)

        llm = get_fintech_agent()

        # Define all available tools
        tools = [
            get_user_balance,
            get_user_accounts,
            get_total_balance,
            get_user_profile,
            get_user_financial_overview,
            get_user_account_summary,
            get_fx_rate,
            compare_fx_rates,
            convert_currency,
            get_bank_info,
            get_available_currencies,
            get_popular_currency_pairs,
            check_account_balance,
            get_all_banks_info,
            get_user_connected_bank_products,
        ]

        # Initialize memory if user_id is provided
        memory = None
        chat_history = []
        if user_id:
            memory = DjangoChatMemory(user_id=user_id, session_id=session_id)
            memory_vars = memory.load_memory_variables({})
            chat_history = memory_vars.get("chat_history", [])

        # Build conversation context
        conversation_context = ""
        if chat_history:
            conversation_context = "Recent conversation:\n"
            for message in chat_history[-4:]:
                if hasattr(message, "content"):
                    role = "User" if isinstance(message, HumanMessage) else "Assistant"
                    conversation_context += f"{role}: {message.content}\n"
            conversation_context += "\n"

        # Create prompt template
        user_context = f"User ID: {user_id}\n" if user_id else ""

        prompt_template = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    f"""You are a professional AI financial advisor for the MCS platform.

                        {conversation_context}{user_context}

                        You have access to tools that provide raw financial data. When you get data from tools:
                        - Format it beautifully with emojis, headers, and clear organization
                        - Use Markdown formatting (tables, bullet points, bold text)
                        - For tabular data, use proper markdown tables with clear headers
                        - Present balances clearly with currency symbols
                        - Right-align numerical columns in tables for better readability
                        - Add helpful insights and recommendations
                        - Be conversational and personable
                        - Use appropriate financial emojis (💰, 🏦, 📊, 💱, etc.)

                        When creating tables:
                        - Use clear, descriptive column headers
                        - Format numbers consistently (e.g., 1,234.56 JOD)
                        - Include currency symbols and percentage signs where appropriate
                        - Keep row data concise but informative

                        Always call the appropriate tools to get current user data rather than making assumptions.""",
                ),
                ("user", "{input}"),
                ("placeholder", "{agent_scratchpad}"),
            ]
        )

        # Create agent
        agent = create_tool_calling_agent(llm, tools, prompt_template)
        agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=False)

        # Execute the agent
        result = agent_executor.invoke({"input": prompt})
        response_content = result["output"]

        # Save conversation to memory
        if memory and user_id:
            try:
                memory.save_context({"input": prompt}, {"output": response_content})
            except Exception as e:
                print(f"Error saving to memory: {e}")

        return response_content

    except Exception as e:
        error_msg = str(e)
        if "GOOGLE_API_KEY" in error_msg:
            return "❌ API key error. Please check configuration."
        elif "rate limit" in error_msg.lower():
            return "⚠️ Rate limit exceeded. Please try again shortly."
        return f"❌ Error: {error_msg}"


def run_agent(prompt: str) -> str:
    """Simple wrapper for running the agent."""
    return run_fintech_agent(prompt)


def test_agent_setup() -> dict:
    """Test the agent setup and return status."""
    result = {
        "api_key_exists": False,
        "llm_created": False,
        "tools_loaded": False,
        "test_query": False,
        "error": None,
    }

    try:
        api_key = os.getenv("GOOGLE_API_KEY")
        result["api_key_exists"] = bool(
            api_key and api_key != "your-google-api-key-here"
        )

        if not result["api_key_exists"]:
            result["error"] = "Google API key is missing or not set properly"
            return result

        llm = get_fintech_agent()
        result["llm_created"] = True

        tools = [get_user_profile]
        result["tools_loaded"] = len(tools) > 0

        response = llm.invoke("Hello, can you help me?")
        result["test_query"] = True
        result["response_type"] = type(response).__name__

        if hasattr(response, "content"):
            content = str(response.content)
            result["response_content"] = (
                content[:100] + "..." if len(content) > 100 else content
            )

    except Exception as e:
        result["error"] = str(e)

    return result
