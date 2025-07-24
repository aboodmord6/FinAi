from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("foreign-exchange/", views.foreign_exchange, name="foreign_exchange"),
    path(
        "get-available-currencies/",
        views.get_available_currencies,
        name="get_available_currencies",
    ),
    # FX API endpoints
    path("api/fx-rate/", views.get_fx_rate, name="get_fx_rate"),
    path("api/convert-currency/", views.convert_currency, name="convert_currency"),
    path("api/popular-rates/", views.get_popular_rates, name="get_popular_rates"),
    path(
        "api/institution-rates/",
        views.get_institution_rates,
        name="get_institution_rates",
    ),
    path("banks/", views.banks, name="banks"),
    path("products/", views.products, name="products"),
    path("chat/", views.chat_page, name="chat"),
    path("about/", views.about, name="about"),
    path("news/", views.news, name="news"),
    path("testimonials/", views.testimonials, name="testimonials"),
    # AI Agent endpoints
    path("ai-assistant/", views.ai_financial_assistant, name="ai_financial_assistant"),
    path("ai-suggestions/", views.get_ai_suggestions, name="get_ai_suggestions"),
    path(
        "ai-welcome/", views.get_personalized_welcome, name="get_personalized_welcome"
    ),
    path("test-user-data/", views.test_user_data, name="test_user_data"),
]
