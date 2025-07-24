#imports
import random
import requests

headers = {
    "x-interactions-id": "application/json",
    "x-idempotency-key": "application/json",
    "x-financial-id": "1",
    "x-jws-signature": "application/json",
    "Accept": "application/json"
}
 # API endpoints as a dictionary
API_ENDPOINTS = {
    "Accounts_GetAccounts": "https://jpcjofsdev.apigw-az-eu.webmethods.io/gateway/Accounts/v0.4.3/accounts",
    "Accounts_GetAccountByAddress": "https://jpcjofsdev.apigw-az-eu.webmethods.io/gateway/Accounts/v0.4.3/accounts/{accountAddress}",
    "ForeignExchangeFX_GetFXs": "https://jpcjofsdev.apigw-az-eu.webmethods.io/gateway/Foreign%20Exchange%20%28FX%29/v0.4.3/institution/FXs",
    "ForeignExchangeFX_GetFXByTargetCurrency": "https://jpcjofsdev.apigw-az-eu.webmethods.io/gateway/Foreign%20Exchange%20%28FX%29/v0.4.3/institution/FXs/{targetCurrency}",
    "ForeignExchangeFX_PostFXQuote": "https://jpcjofsdev.apigw-az-eu.webmethods.io/gateway/Foreign%20Exchange%20%28FX%29/v0.4.3/institution/FXs/quote",
    "ForeignExchangeFX_GetFXQuoteById": "https://jpcjofsdev.apigw-az-eu.webmethods.io/gateway/Foreign%20Exchange%20%28FX%29/v0.4.3/institution/FXs/quote/{quoteId}",
    "Branches_GetBranches": "https://jpcjofsdev.apigw-az-eu.webmethods.io/gateway/Branches/v0.4.3/institution/branches",
    "Branches_GetBranchById": "https://jpcjofsdev.apigw-az-eu.webmethods.io/gateway/Branches/v0.4.3/institution/branches/{branchId}",
    "Fees_GetSSTsFees": "https://jpcjofsdev.apigw-az-eu.webmethods.io/gateway/Fees/v0.4.3/institution/fees/SSTs",
    "FinancialInstitutions_GetFI": "https://jpcjofsdev.apigw-az-eu.webmethods.io/gateway/Financial%20Institutions/v0.4.3/institution",
    "Offers_GetAccountOffers": "https://jpcjofsdev.apigw-az-eu.webmethods.io/gateway/Offers/v0.4.3/accounts/{accountId}/offers",
    "Offers_GetAccountOfferById": "https://jpcjofsdev.apigw-az-eu.webmethods.io/gateway/Offers/v0.4.3/accounts/{accountId}/offers/{offerId}",
    "Offers_GetPublicOffers": "https://jpcjofsdev.apigw-az-eu.webmethods.io/gateway/Offers/v0.4.3/institution/offers",
    "Offers_GetPublicOfferById": "https://jpcjofsdev.apigw-az-eu.webmethods.io/gateway/Offers/v0.4.3/institution/offers/{offerId}",
    "Products_GetProductTree": "http://jpcjofsdev.apigw-az-eu.webmethods.io/gateway/Products/v0.4.3/institution/products/tree",
    "Products_GetAllProducts": "http://jpcjofsdev.apigw-az-eu.webmethods.io/gateway/Products/v0.4.3/institution/products",
    "Products_GetProductById": "http://jpcjofsdev.apigw-az-eu.webmethods.io/gateway/Products/v0.4.3/institution/products/{productId}",
    "SSTs_GetSSTs": "https://jpcjofsdev.apigw-az-eu.webmethods.io/gateway/Self%20Service%20Terminals%20Services/v0.4.3/institution/SSTs",
    "SSTs_GetSSTById": "https://jpcjofsdev.apigw-az-eu.webmethods.io/gateway/Self%20Service%20Terminals%20Services/v0.4.3/institution/SSTs/{sstId}"
}





def _fetch_data(url, method="GET", params=None, json_data=None):
    """
    Generic function to fetch data from an API endpoint.
    """
    try:
        if method.upper() == "GET":
            response = requests.get(url, headers=headers, params=params)
        elif method.upper() == "POST":
            response = requests.post(url, headers=headers, json=json_data, params=params)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
        
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)
        return response.json()
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e.response.status_code} - {e.response.text}")
        return None
    except requests.exceptions.ConnectionError as e:
        print(f"Connection Error: {e}")
        return None
    except requests.exceptions.Timeout as e:
        print(f"Timeout Error: {e}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"An unexpected error occurred: {e}")
        return None


# Accounts Functions
def fetch_accounts(customerID ,params=None, headers_override=None):
    """
    Fetches a list of accounts.
    :param params: Optional dictionary of query parameters (accountStatus, accountType, skip, limit, sort).
    :param headers_override: Optional dictionary to override/add headers (e.g., Authorization, x-interactions-id, etc.)
    :return: JSON response from the API or None on error.
    """
    url = API_ENDPOINTS["Accounts_GetAccounts"]
    merged_headers = headers.copy()
    merged_headers["x-customer-id"] = customerID
    if headers_override:
        merged_headers.update(headers_override)
    return _fetch_data(url, params=params)

# Foreign Exchange (FX) Functions
def fetch_foreign_exchange_fxs(params=None):
    """
    Fetches a list of Foreign Exchange objects.
    :param params: Optional dictionary of query parameters.
    :return: JSON response from the API or None on error.
    """
    url = API_ENDPOINTS["ForeignExchangeFX_GetFXs"]
    return _fetch_data(url, params=params)

def fetch_foreign_exchange_fx_by_target_currency(target_currency, params=None):
    """
    Fetches Foreign Exchange information for a specific target currency.
    :param target_currency: The currency code to convert to (e.g., "USD").
    :param params: Optional dictionary of query parameters.
    :return: JSON response from the API or None on error.
    """
    url = API_ENDPOINTS["ForeignExchangeFX_GetFXByTargetCurrency"].format(targetCurrency=target_currency)
    return _fetch_data(url, params=params)

def post_foreign_exchange_fx_quote(json_data, params=None):
    """
    Creates a quote request for a specific currency.
    :param json_data: Dictionary containing the request body (e.g., sourceCurrency, targetCurrency, sourceAmount).
    :param params: Optional dictionary of query parameters.
    :return: JSON response from the API or None on error.
    """
    url = API_ENDPOINTS["ForeignExchangeFX_PostFXQuote"]
    return _fetch_data(url, method="POST", json_data=json_data, params=params)

def fetch_foreign_exchange_fx_quote_by_id(quote_id, params=None):
    """
    Retrieves an FX quote using a quote identifier.
    :param quote_id: The ID of the FX quote.
    :param params: Optional dictionary of query parameters.
    :return: JSON response from the API or None on error.
    """
    url = API_ENDPOINTS["ForeignExchangeFX_GetFXQuoteById"].format(quoteId=quote_id)
    return _fetch_data(url, params=params)

# Branches Functions
def fetch_branches(params=None):
    """
    Fetches a list of bank branches.
    :param params: Optional dictionary of query parameters (e.g., isAvailable, hasAccessiblityFeatures).
    :return: JSON response from the API or None on error.
    """
    url = API_ENDPOINTS["Branches_GetBranches"]
    return _fetch_data(url, params=params)

def fetch_branch_by_id(branch_id, params=None):
    """
    Fetches detailed information about a specific bank branch by its ID.
    :param branch_id: The ID of the branch to retrieve.
    :param params: Optional dictionary of query parameters.
    :return: JSON response from the API or None on error.
    """
    url = API_ENDPOINTS["Branches_GetBranchById"].format(branchId=branch_id)
    return _fetch_data(url, params=params)

# Fees Functions
def fetch_fees_ssts(params=None):
    """
    Fetches a list of fees charged by Self-Service Terminals (SSTs).
    :param params: Optional dictionary of query parameters (e.g., service).
    :return: JSON response from the API or None on error.
    """
    url = API_ENDPOINTS["Fees_GetSSTsFees"]
    return _fetch_data(url, params=params)

# Financial Institutions Functions
def fetch_financial_institutions(params=None):
    """
    Fetches details of a Financial Institution.
    :param params: Optional dictionary of query parameters.
    :return: JSON response from the API or None on error.
    """
    url = API_ENDPOINTS["FinancialInstitutions_GetFI"]
    return _fetch_data(url, params=params)

# Offers Functions
def fetch_offers_account_offers(account_id, params=None):
    """
    Fetches a list of offers for a specific account.
    :param account_id: The ID of the account.
    :param params: Optional dictionary of query parameters (e.g., productId).
    :return: JSON response from the API or None on error.
    """
    url = API_ENDPOINTS["Offers_GetAccountOffers"].format(accountId=account_id)
    return _fetch_data(url, params=params)

def fetch_offers_account_offer_by_id(account_id, offer_id, params=None):
    """
    Retrieves a specific offer for a specific account by account ID and offer ID.
    :param account_id: The ID of the account.
    :param offer_id: The ID of the offer to retrieve.
    :param params: Optional dictionary of query parameters.
    :return: JSON response from the API or None on error.
    """
    url = API_ENDPOINTS["Offers_GetAccountOfferById"].format(accountId=account_id, offerId=offer_id)
    return _fetch_data(url, params=params)

def fetch_offers_public_offers(params=None):
    """
    Fetches a list of all public offers from the financial institution.
    :param params: Optional dictionary of query parameters (e.g., productId).
    :return: JSON response from the API or None on error.
    """
    url = API_ENDPOINTS["Offers_GetPublicOffers"]
    return _fetch_data(url, params=params)

def fetch_offers_public_offer_by_id(offer_id, params=None):
    """
    Retrieves a specific public offer by its ID.
    :param offer_id: The ID of the public offer to retrieve.
    :param params: Optional dictionary of query parameters.
    :return: JSON response from the API or None on error.
    """
    url = API_ENDPOINTS["Offers_GetPublicOfferById"].format(offerId=offer_id)
    return _fetch_data(url, params=params)

# Products Functions
def fetch_products_product_tree(params=None):
    """
    Fetches hierarchical data of available financial products (product tree).
    :param params: Optional dictionary of query parameters (e.g., productNodeMaxLevel, productStartPath).
    :return: JSON response from the API or None on error.
    """
    url = API_ENDPOINTS["Products_GetProductTree"]
    return _fetch_data(url, params=params)

def fetch_products_all_products(params=None):
    """
    Retrieves a list of all products at the Financial Institution.
    :param params: Optional dictionary of query parameters (e.g., productType).
    :return: JSON response from the API or None on error.
    """
    url = API_ENDPOINTS["Products_GetAllProducts"]
    return _fetch_data(url, params=params)

def fetch_products_product_by_id(product_id, params=None):
    """
    Retrieves a specific product by its ID.
    :param product_id: The ID of the product to retrieve.
    :param params: Optional dictionary of query parameters.
    :return: JSON response from the API or None on error.
    """
    url = API_ENDPOINTS["Products_GetProductById"].format(productId=product_id)
    return _fetch_data(url, params=params)

# Self Service Terminals Services Functions
def fetch_ssts_ssts(params=None):
    """
    Fetches information about Self-Service Terminals (SSTs).
    :param params: Optional dictionary of query parameters (e.g., sstType, isAvailable).
    :return: JSON response from the API or None on error.
    """
    url = API_ENDPOINTS["SSTs_GetSSTs"]
    return _fetch_data(url, params=params)

def fetch_ssts_sst_by_id(sst_id, params=None):
    """
    Retrieves detailed information about a specific Self-Service Terminal (SST) by its ID.
    :param sst_id: The ID of the SST to retrieve.
    :param params: Optional dictionary of query parameters.
    :return: JSON response from the API or None on error.
    """
    url = API_ENDPOINTS["SSTs_GetSSTById"].format(sstId=sst_id)
    return _fetch_data(url, params=params)



print(fetch_financial_institutions())