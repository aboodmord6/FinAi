from django.views.decorators.http import require_GET, require_POST
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Avg, Min, Max
from django.utils import timezone
from decimal import Decimal
from typing import Any, Dict, List
import json

from .models import FinancialInstitution, Accounts, FXRate, FinancialProduct
from .services.agent import run_fintech_agent, test_agent_setup


# Main FX page view
@login_required
def foreign_exchange(request) -> HttpResponse:
    # Get all available currencies from the database
    currencies = sorted(
        list(
            set(
                FXRate.objects.values_list("source_currency", flat=True).union(
                    FXRate.objects.values_list("target_currency", flat=True)
                )
            )
        )
    )  # type: ignore[attr-defined]

    # Get recent FX rates for display
    recent_rates = FXRate.objects.select_related("FinancialInstitution").order_by(
        "-effective_date"
    )[
        :10
    ]  # type: ignore[attr-defined]

    # Get popular currency pairs
    popular_pairs = ["USD/EUR", "USD/GBP", "EUR/GBP", "USD/JPY", "USD/JOD"]
    popular_rates = []

    for pair in popular_pairs:
        if "/" in pair:
            source, target = pair.split("/")
            rate = (
                FXRate.objects.filter(source_currency=source, target_currency=target)
                .select_related("FinancialInstitution")
                .order_by("-effective_date")
                .first()
            )  # type: ignore[attr-defined]

            if rate:
                popular_rates.append(rate)

    # Get all financial institutions
    banks = FinancialInstitution.objects.all()  # type: ignore[attr-defined]

    context = {
        "currencies": currencies,
        "recent_rates": recent_rates,
        "popular_rates": popular_rates,
        "banks": banks,
        "current_time": timezone.now(),
    }

    return render(request, "Main/foreign_exchange.html", context)


# API endpoint to get FX rates for a specific currency pair
@login_required
@require_GET
def get_fx_rate(request) -> JsonResponse:
    """Get FX rate for a specific currency pair."""
    try:
        source_currency = request.GET.get("source", "").upper()
        target_currency = request.GET.get("target", "").upper()

        if not source_currency or not target_currency:
            return JsonResponse(
                {"error": "Source and target currencies are required"}, status=400
            )

        # Get the latest rate for this pair
        rate = (
            FXRate.objects.filter(
                source_currency=source_currency, target_currency=target_currency
            )
            .select_related("FinancialInstitution")
            .order_by("-effective_date")
            .first()
        )  # type: ignore[attr-defined]

        if not rate:
            return JsonResponse(
                {"error": "Rate not found for this currency pair"}, status=404
            )

        # Get rates from all institutions for comparison
        all_rates = (
            FXRate.objects.filter(
                source_currency=source_currency, target_currency=target_currency
            )
            .select_related("FinancialInstitution")
            .order_by("-effective_date")
        )  # type: ignore[attr-defined]

        # Calculate statistics
        rates_data = []
        for r in all_rates:
            rates_data.append(
                {
                    "institution": r.FinancialInstitution.name,
                    "rate": float(r.conversion_value),
                    "inverse_rate": float(r.inverse_conversion_value),
                    "min_rate": (
                        float(r.min_conversion_value)
                        if r.min_conversion_value
                        else None
                    ),
                    "max_rate": (
                        float(r.max_conversion_value)
                        if r.max_conversion_value
                        else None
                    ),
                    "effective_date": r.effective_date.isoformat(),
                }
            )

        # Calculate min/max rates across all institutions
        if rates_data:
            min_rate = min(r["rate"] for r in rates_data)
            max_rate = max(r["rate"] for r in rates_data)
            avg_rate = sum(r["rate"] for r in rates_data) / len(rates_data)
        else:
            min_rate = max_rate = avg_rate = float(rate.conversion_value)

        return JsonResponse(
            {
                "source_currency": source_currency,
                "target_currency": target_currency,
                "current_rate": float(rate.conversion_value),
                "inverse_rate": float(rate.inverse_conversion_value),
                "min_rate": min_rate,
                "max_rate": max_rate,
                "avg_rate": avg_rate,
                "institution": rate.FinancialInstitution.name,
                "effective_date": rate.effective_date.isoformat(),
                "all_rates": rates_data,
            }
        )

    except Exception as e:
        return JsonResponse({"error": f"Error fetching rate: {str(e)}"}, status=500)


# API endpoint to convert currency amounts
@login_required
@require_GET
def convert_currency(request) -> JsonResponse:
    """Convert amount from one currency to another."""
    try:
        amount = Decimal(request.GET.get("amount", "1"))
        source_currency = request.GET.get("source", "").upper()
        target_currency = request.GET.get("target", "").upper()

        if not source_currency or not target_currency:
            return JsonResponse(
                {"error": "Source and target currencies are required"}, status=400
            )

        # Get the latest rate
        rate = (
            FXRate.objects.filter(
                source_currency=source_currency, target_currency=target_currency
            )
            .order_by("-effective_date")
            .first()
        )  # type: ignore[attr-defined]

        if not rate:
            return JsonResponse(
                {"error": "Rate not found for this currency pair"}, status=404
            )

        converted_amount = amount * rate.conversion_value

        return JsonResponse(
            {
                "source_amount": float(amount),
                "source_currency": source_currency,
                "target_amount": float(converted_amount),
                "target_currency": target_currency,
                "rate": float(rate.conversion_value),
                "institution": rate.FinancialInstitution.name,
            }
        )

    except (ValueError, TypeError):
        return JsonResponse({"error": "Invalid amount provided"}, status=400)
    except Exception as e:
        return JsonResponse(
            {"error": f"Error converting currency: {str(e)}"}, status=500
        )


# API endpoint to get popular rates
@login_required
@require_GET
def get_popular_rates(request) -> JsonResponse:
    """Get popular currency pair rates."""
    try:
        popular_pairs = ["USD/EUR", "USD/GBP", "EUR/GBP", "USD/JPY", "USD/JOD"]
        rates_data = []

        for pair in popular_pairs:
            source, target = pair.split("/")

            # Get the latest rate for this pair
            rate = (
                FXRate.objects.filter(source_currency=source, target_currency=target)
                .select_related("FinancialInstitution")
                .order_by("-effective_date")
                .first()
            )  # type: ignore[attr-defined]

            if rate:
                # Get previous rate for comparison
                prev_rate = (
                    FXRate.objects.filter(
                        source_currency=source, target_currency=target
                    )
                    .order_by("-effective_date")
                    .exclude(id=rate.id)
                    .first()
                )  # type: ignore[attr-defined]

                # Calculate change percentage
                change_percent = 0.0
                if prev_rate:
                    change_percent = (
                        (rate.conversion_value - prev_rate.conversion_value)
                        / prev_rate.conversion_value
                    ) * 100

                rates_data.append(
                    {
                        "pair": pair,
                        "source": source,
                        "target": target,
                        "rate": float(rate.conversion_value),
                        "change_percent": round(change_percent, 2),
                        "institution": rate.FinancialInstitution.name,
                        "effective_date": rate.effective_date.isoformat(),
                    }
                )

        return JsonResponse({"popular_rates": rates_data})

    except Exception as e:
        return JsonResponse(
            {"error": f"Error fetching popular rates: {str(e)}"}, status=500
        )


# API endpoint to get rates by institution
@login_required
@require_GET
def get_institution_rates(request) -> JsonResponse:
    """Get FX rates for a specific institution."""
    try:
        institution_id = request.GET.get("institution_id")
        source_currency = request.GET.get("source", "").upper()
        target_currency = request.GET.get("target", "").upper()

        if not institution_id:
            return JsonResponse({"error": "Institution ID is required"}, status=400)

        # Build query
        query = FXRate.objects.filter(FinancialInstitution_id=institution_id)  # type: ignore[attr-defined]

        if source_currency:
            query = query.filter(source_currency=source_currency)
        if target_currency:
            query = query.filter(target_currency=target_currency)

        rates = query.select_related("FinancialInstitution").order_by("-effective_date")

        rates_data = []
        for rate in rates:
            rates_data.append(
                {
                    "source_currency": rate.source_currency,
                    "target_currency": rate.target_currency,
                    "rate": float(rate.conversion_value),
                    "inverse_rate": float(rate.inverse_conversion_value),
                    "min_rate": (
                        float(rate.min_conversion_value)
                        if rate.min_conversion_value
                        else None
                    ),
                    "max_rate": (
                        float(rate.max_conversion_value)
                        if rate.max_conversion_value
                        else None
                    ),
                    "effective_date": rate.effective_date.isoformat(),
                    "institution": rate.FinancialInstitution.name,
                }
            )

        return JsonResponse({"rates": rates_data})

    except Exception as e:
        return JsonResponse(
            {"error": f"Error fetching institution rates: {str(e)}"}, status=500
        )


# Other existing views
@login_required
def index(request) -> HttpResponse:
    accounts = Accounts.objects.filter(user=request.user).select_related(
        "financial_institution", "product"
    )  # type: ignore[attr-defined]
    context = {"accounts": accounts}
    return render(request, "Main/index.html", context)


@login_required
def banks(request) -> HttpResponse:
    financial_institutions = FinancialInstitution.objects.all().select_related(
        "address"
    )  # type: ignore[attr-defined]
    context = {"banks": financial_institutions}
    return render(request, "Main/banks.html", context)


@login_required
def products(request) -> HttpResponse:
    """Display financial products grouped by institution."""
    # Fetch institutions that have at least one product
    institutions = FinancialInstitution.objects.all()  # type: ignore[attr-defined]

    institutions_products = []
    global_product_index = 0
    # DaisyUI color scheme
    colors = ["primary", "secondary", "accent", "info", "success", "warning"]

    for inst in institutions:
        product_qs = FinancialProduct.objects.filter(
            FinancialInstitution=inst
        ).select_related(
            "category"
        )  # type: ignore[attr-defined]
        if product_qs.exists():
            # Add color index to each product
            products_with_colors = []
            for product in product_qs:
                product.color_hue = colors[global_product_index % len(colors)]
                products_with_colors.append(product)
                global_product_index += 1

            institutions_products.append(
                {
                    "institution": inst,
                    "products": products_with_colors,
                }
            )

    # Get unique categories for filter
    categories = set()
    all_institutions = []
    for entry in institutions_products:
        all_institutions.append(entry["institution"])
        for product in entry["products"]:
            categories.add(product.category.name)

    context = {
        "institutions_products": institutions_products,
        "categories": sorted(categories),
        "institutions": all_institutions,
    }

    return render(request, "Main/products.html", context)


@login_required
@require_POST
def ai_financial_assistant(request) -> JsonResponse:
    """
    AI-powered financial assistant endpoint using LangChain.
    """
    try:
        # Get user message from request
        user_message = request.POST.get("message", "").strip()
        session_id = request.POST.get("session_id", "").strip()

        if not user_message:
            return JsonResponse({"error": "Please provide a message"}, status=400)

        # Debug: Ensure user_id is being passed correctly
        user_id = request.user.id

        # Run the fintech agent with memory
        response = run_fintech_agent(
            user_message, user_id=user_id, session_id=session_id
        )

        return JsonResponse(
            {"response": response, "timestamp": timezone.now().isoformat()}
        )

    except Exception as e:
        return JsonResponse(
            {"error": f"Sorry, I encountered an error: {str(e)}"},
            status=500,
        )


@login_required
def chat_page(request) -> HttpResponse:
    """
    Chat page for AI financial assistant.
    """
    # Get user's financial context for personalization
    user_accounts = Accounts.objects.filter(user=request.user).select_related(
        "financial_institution"
    )  # type: ignore[attr-defined]
    account_count = user_accounts.count()

    # Get unique banks and currencies
    banks = user_accounts.values_list(
        "financial_institution__name", flat=True
    ).distinct()
    currencies = user_accounts.values_list("account_currency", flat=True).distinct()

    # Get current time for greeting
    from datetime import datetime

    current_hour = datetime.now().hour

    if current_hour < 12:
        time_greeting = "Good morning"
    elif current_hour < 17:
        time_greeting = "Good afternoon"
    else:
        time_greeting = "Good evening"

    return render(
        request,
        "Main/chat.html",
        {
            "page_title": "AI Financial Assistant",
            "user_name": request.user.first_name or request.user.username,
            "user_full_name": f"{request.user.first_name} {request.user.last_name}".strip(),
            "time_greeting": time_greeting,
            "account_count": account_count,
            "banks": list(banks),
            "currencies": list(currencies),
            "has_accounts": account_count > 0,
        },
    )


@login_required
@require_GET
def get_ai_suggestions(request) -> JsonResponse:
    """
    Get AI-powered suggestions for financial queries.
    """
    try:
        # Get user's financial context for personalized suggestions
        user_accounts = Accounts.objects.filter(user=request.user).select_related(
            "financial_institution"
        )  # type: ignore[attr-defined]
        account_count = user_accounts.count()

        # Get unique banks and currencies
        banks = list(
            user_accounts.values_list(
                "financial_institution__name", flat=True
            ).distinct()
        )
        currencies = list(
            user_accounts.values_list("account_currency", flat=True).distinct()
        )

        # Base personalized suggestions
        suggestions = [
            f"Hello! Give me a personalized greeting",
            "Show me my profile information",
            "Give me my financial overview",
        ]

        # Add balance-related suggestions if user has accounts
        if account_count > 0:
            suggestions.extend(
                [
                    "Show me my account balances",
                    "What's my total balance?",
                    "Give me a balance summary",
                    "Show me my account summary with insights",
                ]
            )

            # Add bank-specific suggestions
            if banks:
                suggestions.append(f"Check my balance at {banks[0]}")
                if len(banks) > 1:
                    suggestions.append(f"Compare my accounts across {len(banks)} banks")

        # Add currency-specific suggestions
        if len(currencies) > 1:
            suggestions.extend(
                [
                    f"Convert between my currencies ({', '.join(currencies[:2])})",
                    f"Compare rates for my currencies",
                ]
            )
        elif len(currencies) == 1:
            main_currency = currencies[0]
            if main_currency != "USD":
                suggestions.append(f"Convert {main_currency} to USD")
            if main_currency != "EUR":
                suggestions.append(f"Convert {main_currency} to EUR")

        # Add general suggestions
        suggestions.extend(
            [
                "What are the best USD to EUR exchange rates today?",
                "Compare exchange rates across all banks",
                "Convert 1000 USD to JOD",
                "Show me information about Arab Bank",
                "What currencies are available for exchange?",
                "What are the popular currency pairs?",
                "Which bank offers the best rates for USD/EUR?",
            ]
        )

        # Limit to top 12 suggestions
        suggestions = suggestions[:12]

        return JsonResponse({"suggestions": suggestions})

    except Exception as e:
        return JsonResponse({"error": "Unable to load suggestions"}, status=500)


@login_required
@require_GET
def get_personalized_welcome(request) -> JsonResponse:
    """
    Get personalized welcome message from AI.
    """
    try:
        from .services.agent import run_fintech_agent

        user_id = request.user.id
        user_name = request.user.first_name or request.user.username
        user_full_name = f"{request.user.first_name} {request.user.last_name}".strip()

        # Use the agent to generate a personalized greeting
        greeting_message = run_fintech_agent("hello", user_id=user_id)

        return JsonResponse(
            {
                "message": greeting_message,
                "user_id": user_id,
                "user_name": user_name,
                "user_full_name": user_full_name,
            }
        )

    except Exception as e:
        return JsonResponse(
            {"error": f"Sorry, I encountered an error: {str(e)}"},
            status=500,
        )


@login_required
@require_GET
def test_user_data(request) -> JsonResponse:
    """
    Debug endpoint to test user data retrieval.
    """
    try:
        user_id = request.user.id
        user_name = request.user.first_name or request.user.username
        user_full_name = f"{request.user.first_name} {request.user.last_name}".strip()

        from .services.agent import get_user_profile, run_fintech_agent

        profile_data = get_user_profile.invoke({"user_id": user_id})  # type: ignore
        greeting_data = run_fintech_agent("hello", user_id=user_id)

        return JsonResponse(
            {
                "user_id": user_id,
                "user_name": user_name,
                "user_full_name": user_full_name,
                "profile_data": profile_data,
                "greeting_data": greeting_data,
            }
        )

    except Exception as e:
        return JsonResponse(
            {"error": f"Error testing user data: {str(e)}"},
            status=500,
        )


@login_required
def about(request) -> HttpResponse:
    return render(request, "Main/about.html")


@login_required
def news(request) -> HttpResponse:
    return render(request, "Main/news.html")


@login_required
def testimonials(request) -> HttpResponse:
    return render(request, "Main/testimonials.html")


def get_available_currencies(request) -> JsonResponse:
    currencies = sorted(
        list(
            set(
                FXRate.objects.values_list("source_currency", flat=True).union(
                    FXRate.objects.values_list("target_currency", flat=True)
                )
            )
        )
    )  # type: ignore[attr-defined]
    return JsonResponse(currencies, safe=False)
