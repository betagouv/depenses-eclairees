import logging
import optparse
import os
import platform
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, date
from typing import Optional

from cloakbrowser import launch, launch_context

logger = logging.getLogger(__name__)

# Determine select-all keyboard shortcut based on OS
SELECT_ALL_MODIFIER = "Meta" if platform.system() == "Darwin" else "Control"


@dataclass
class SearchParams:
    """Parameters for searching invoices on CPRO."""
    service: Optional[str] = None
    provider_name: Optional[str] = None
    provider_siret: Optional[str] = None
    provider_siren: Optional[str] = None
    num_ej: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None


def parse_args():
    parser = optparse.OptionParser()
    parser.add_option("--start", dest="start", help="Start date in ISO format (YYYY-MM-DD)")
    parser.add_option("--end", dest="end", help="End date in ISO format (YYYY-MM-DD)")
    parser.add_option("--service", dest="service", help="Service code")
    parser.add_option("--headed", action="store_true", default=False, help="Run in headed mode")
    parser.add_option("--provider-name", dest="provider_name", help="Provider name (required if provider is specified)")
    parser.add_option("--provider-siret", dest="provider_siret", help="Provider SIRET (mutually exclusive with --provider-siren)")
    parser.add_option("--provider-siren", dest="provider_siren", help="Provider SIREN (mutually exclusive with --provider-siret)")
    parser.add_option("--num-ej", dest="num_ej", help="Numéro EJ (Bon de commande)")
    options, args = parser.parse_args()
    return options


def init_context(headless: bool = True):
    """Initialize browser context with cookies and download handler."""
    logger.info("Initializing context...")
    os.makedirs("../downloads", exist_ok=True)
    ctx = launch_context(headless=headless)
    ctx.add_cookies([
        { "name": "JSESSIONID",
          "value": os.environ["JSESSIONID"],
          "domain": "cpro.chorus-pro.gouv.fr",
          "path": "/cpp",
        },
    ])
    page = ctx.new_page()
    logger.info("Context initialized.")
    return ctx, page


def init_search_page(page):
    """Navigate to the invoice search page and fill the static form criteria."""
    logger.info(f"Initializing search page")

    # Ouverture de la page
    page.goto("https://cpro.chorus-pro.gouv.fr/cpp/rechercheFactures")

    # Sélection de l'état Mise en paiement
    page.select_option("select[name='listeResultats.critere.etatCourant']", value="MISE_EN_PAIEMENT")

    logger.info("Search page initialized.")


def open_advanced_search_section(page):
    expander = page.locator("[data-target='#GDP_RechercheFacture_CriteresPanneau_Body']")
    is_expanded = expander.get_attribute("aria-expanded") == "true"
    if not is_expanded:
        expander.click()
    page.locator("#GFR_RechercheFactureEtatAcompteRecus_Criteres_BoutonRechercher").scroll_into_view_if_needed()


def fill_service(page, service: str):
    # Selection du service
    page.select_option("select[name='listeResultats.critere.structureDestinataireId']", value="568055")
    page.click("#GFR_RechercheFacturesRecues_Criteres_BtnRechercherService")
    page.fill("input[name='listeServices.critere.code']", service)
    page.click("button[type='submit']")
    page.click("#selection0")


def fill_provider(page, provider_name: str, provider_siret: str = None, provider_siren: str = None):
    """Fill the provider search field. Requires either siret or siren (but not both) and a name.
    
    Args:
        page: The Playwright page object
        provider_name: The name of the provider (required)
        provider_siret: The SIRET of the provider (optional, mutually exclusive with provider_siren)
        provider_siren: The SIREN of the provider (optional, mutually exclusive with provider_siret)
    """
    if provider_siret and provider_siren:
        raise ValueError("Cannot provide both siret and siren. Please provide only one.")
    if not provider_siret and not provider_siren:
        raise ValueError("Must provide either siret or siren.")
    
    identifier = provider_siret or provider_siren
    logger.info(f"Filling provider: name={provider_name}, identifier={identifier}")
    
    # Click on the provider select2 container to open the dropdown
    page.click("#select2-GFR_RechercheFacturesRecues_Criteres_StructureFournisseurGFR_RechercheFacturesRecues-container")
    
    # Type the siret or siren
    page.keyboard.type(identifier)
    
    # Wait for results and click the first one
    page.click("#select2-GFR_RechercheFacturesRecues_Criteres_StructureFournisseurGFR_RechercheFacturesRecues-results li:first-child")
    
    # If siren is provided, check if SIREN checkbox is disabled and enable it if needed
    if provider_siren:
        siren_checkbox = page.locator("#TRA_Recherche_Factures_Coche_SIREN")
        is_disabled = siren_checkbox.get_attribute("disabled")
        if is_disabled:
            logger.info("SIREN checkbox is disabled, enabling it...")
            page.evaluate("""() => {
                const el = document.getElementById('TRA_Recherche_Factures_Coche_SIREN');
                if (el) el.disabled = false;
            }""")
        # Click the label to select SIREN
        page.click("label[for='TRA_Recherche_Factures_Coche_SIREN']")
    
        # Assert that SIREN checkbox is checked
        assert page.locator("#TRA_Recherche_Factures_Coche_SIREN").is_checked(), "SIREN checkbox should be checked"
        assert page.input_value("input[name='rechercheParSiren']") == "true", "rechercheParSiren should be true"
    
    logger.info(f"Provider filled successfully: {provider_name}")


def fill_num_ej(page, num_ej: str):
    """Fill the numéro bon de commande (EJ) field.
    
    Args:
        page: The Playwright page object
        num_ej: The numéro EJ (bon de commande) to fill
    """
    logger.info(f"Filling numéro EJ: {num_ej}")
    open_advanced_search_section(page)
    page.fill("input[name='listeResultats.critere.numeroBonDeCommande']", num_ej)
    logger.info(f"Numéro EJ filled successfully: {num_ej}")


def fill_date_range(page, start_date: date, end_date: date):
    """Fill the date range fields with start and end dates.
    
    Args:
        page: The Playwright page object
        start_date: The start date to fill in the start field
        end_date: The end date to fill in the end field
    """
    open_advanced_search_section(page)
    str_start = start_date.strftime("%d/%m/%Y")
    str_end = end_date.strftime("%d/%m/%Y")
    logger.info(f"Filling date range: {start_date} to {end_date}")
    page.click("input[name='listeResultats.critere.dateHeureEtatCourantDebut']")
    page.keyboard.press(f"{SELECT_ALL_MODIFIER}+a")
    page.keyboard.type(str_start)
    page.click("input[name='listeResultats.critere.dateHeureEtatCourantFin']")
    page.keyboard.press(f"{SELECT_ALL_MODIFIER}+a")
    page.keyboard.type(str_end)


def submit_form(page) -> bool:
    """Submit the search form by clicking the search button.
    Returns True if results were found, False otherwise.
    
    Args:
        page: The Playwright page object
    """
    logger.info("Submitting search form...")
    page.click("#GFR_RechercheFactureEtatAcompteRecus_Criteres_BoutonRechercher")
    page.wait_for_load_state("load")
    logger.info("Search form submitted.")
    
    # Check if table with "Résultats de la recherche" caption exists (indicates results were found)
    if page.query_selector("table caption:has-text('Résultats de la recherche')") is None:
        logger.info("No results found.")
        return False
    return True


def check_form_arguments(page, start_date: date, end_date: date):
    """Verify that the form fields have the expected values.

    Args:
        page: The Playwright page object
        str_date: The date string in DD/MM/YYYY format
    """
    str_start = start_date.strftime("%d/%m/%Y")
    str_end = end_date.strftime("%d/%m/%Y")
    assert page.input_value("input[name='listeResultats.critere.dateHeureEtatCourantDebut']") == str_start
    assert page.input_value("input[name='listeResultats.critere.dateHeureEtatCourantFin']") == str_end


def go_next_page(page) -> bool:
    """Check for a next page button and click it if available. Returns True if a new page was loaded, False otherwise."""
    next_button = page.locator("button[title='Aller à la page suivante du tableau']")
    is_disabled = next_button.get_attribute("disabled")
    if is_disabled:
        logger.info("No next page available.")
        return False
    
    logger.info("Navigating to next page...")
    next_button.click()
    page.wait_for_load_state("load")
    logger.info("Next page loaded.")
    return True


def build_filename(service: str, provider_siret: str = None, provider_siren: str = None, num_ej: str = None, start_date: date = None, end_date: date = None, page_number: str = None):
    """Build a filename based on the provided parameters.
    Order: num_ej -> service -> provider (siret/siren) -> num_ej -> date -> page_number
    
    Args:
        service: The service code (required)
        provider_siret: Optional provider SIRET
        provider_siren: Optional provider SIREN
        num_ej: Optional numéro EJ
        start_date: Optional start date for the file
        end_date: Optional end date for the file
        page_number: Optional page number
    
    Returns:
        A sanitized filename string
    """
    parts = [service]
    
    # Provider identifier (prefer siret, fallback to siren)
    provider_id = provider_siret or provider_siren
    if provider_id:
        parts.append(provider_id)
    
    if num_ej:
        parts.append(num_ej)
    
    if date:
        parts.append(date.strftime("%Y%m%d"))
    
    if page_number:
        parts.append(page_number)
    
    return "_".join(parts) + ".zip"


def download_items_bulk(page, service: str, provider_siret: str = None, provider_siren: str = None, num_ej: str = None, start_date: date = None, end_date: date = None):
    """Select all items on the current page and trigger bulk download.
    
    Args:
        page: The Playwright page object
        service: The service code
        provider_siret: Optional provider SIRET to include in filename
        provider_siren: Optional provider SIREN to include in filename
        num_ej: Optional numéro EJ to include in filename
        start_date: Optional start date to include in filename
        end_date: Optional end date to include in filename
    """
    # Get current page number from value attribute of the active page button
    page_button = page.locator("li.paginate__page.paginate__page_active button[name='listeResultats.page']")
    page_number = page_button.get_attribute("value")
    
    filename = build_filename(service, provider_siret, provider_siren, num_ej, start_date, end_date, page_number)
    filepath = f"../downloads/{filename}"
    
    if os.path.exists(filepath):
        logger.info(f"File {filename} already exists, skipping download for service={service}, start_date={start_date}, end_date={end_date}, page={page_number}")
        return
    
    # Verify date fields have the expected values (only if start_date and end_date are provided)
    if start_date and end_date:
        check_form_arguments(page, start_date, end_date)
    
    logger.info(f"Downloading items for service={service}, start_date={start_date}, end_date={end_date}, page={page_number}")

    checkbox = page.locator("#actualiserDEFAULT-1")
    checkbox.locator("xpath=ancestor::span").click()
    page.click("#Synthese_Btn_TelechargerEnMasse")

    with page.expect_download(timeout=5 * 60 * 1000) as download_info:
        page.click("#GDP_Telechargementfacture_BoutonTelecharger")
    download = download_info.value
    assert download_info.is_done(), "Download should be done."
    download.save_as(filepath)
    logger.info(f"Saved as {filename}")


def download_items(page):
    """Download items one by one from the current page.
    
    Iterates over all buttons with name='Synthese_Btn_TelechargerUnitaire',
    extracts the data-value attribute (id_chorus), clicks the button,
    and saves the download as facture_<id_chorus>.zip.
    
    Args:
        page: The Playwright page object
    """
    # Find all individual download buttons
    download_buttons = page.locator("button[name='Synthese_Btn_TelechargerUnitaire']")
    
    # Get the count of buttons
    button_count = download_buttons.count()
    logger.info(f"Found {button_count} items to download individually")

    stats = {"files": button_count, "download": 0, "skip": 0, "error": 0}
    # Iterate over each button
    for i in range(button_count):
        # Get the i-th button
        button = download_buttons.nth(i)
        
        # Get the data-value attribute which contains the id_chorus
        id_chorus = button.get_attribute("data-value")
        if not id_chorus:
            logger.warning(f"Button {i} has no data-value attribute, skipping")
            stats["error"] += 1
            continue
        
        filename = f"facture_{id_chorus}.zip"
        filepath = f"../downloads/factures/{filename}"
        
        if os.path.exists(filepath):
            logger.info(f"File {filename} already exists, skipping download for id_chorus={id_chorus}")
            stats["skip"] += 1
            continue
        
        logger.info(f"Downloading item {i+1}/{button_count} with id_chorus={id_chorus}")
        
        # Click the button to trigger download
        button.click()
        with page.expect_download(timeout=5 * 60 * 1000) as download_info:
            page.click("#GDP_Telechargementfacture_BoutonTelecharger")

        download = download_info.value
        assert download_info.is_done(), "Download should be done."
        download.save_as(filepath)
        logger.info(f"Saved as {filename}")
        stats["download"] += 1

    return stats


def search_and_download(page, params: SearchParams):
    """Search for invoices based on the provided parameters and download all results.
    
    Args:
        page: The Playwright page object
        params: SearchParams containing all search criteria
    """
    logger.info(f"Starting search and download with params: {params}")
    
    # Initialize search page once
    init_search_page(page)
    
    # Fill service
    if params.service:
        fill_service(page, params.service)
    
    # Fill provider if specified
    if params.provider_name and (params.provider_siret or params.provider_siren):
        fill_provider(page, params.provider_name, params.provider_siret, params.provider_siren)
    
    # Fill numéro EJ if specified
    if params.num_ej:
        fill_num_ej(page, params.num_ej)
    
    # Fill date range
    if params.start_date and params.end_date:
        fill_date_range(page, params.start_date, params.end_date)
    
    logger.info(f"Starting download for service={params.service}, num_ej={params.num_ej}")
    if not submit_form(page):
        logger.info("No results found.")
        return
    
    # Download all pages
    while True:
        stats = download_items(page)
        logger.info("Downloads: %s", stats)
        if not go_next_page(page):
            break


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    options = parse_args()
    
    # Parse optional date range
    start_date = date.fromisoformat(options.start) if options.start else None
    end_date = date.fromisoformat(options.end) if options.end else None
    
    # Create search parameters
    params = SearchParams(
        service=options.service,
        provider_name=options.provider_name,
        provider_siret=options.provider_siret,
        provider_siren=options.provider_siren,
        num_ej=options.num_ej,
        start_date=start_date,
        end_date=end_date,
    )
    
    # Validate provider options
    has_provider = params.provider_name or params.provider_siret or params.provider_siren
    if has_provider:
        if not params.provider_name:
            raise ValueError("Provider name is required when specifying a provider. Use --provider-name.")
        if not params.provider_siret and not params.provider_siren:
            raise ValueError("Must provide either --provider-siret or --provider-siren when specifying a provider.")
        if params.provider_siret and params.provider_siren:
            raise ValueError("Cannot provide both --provider-siret and --provider-siren. Please provide only one.")

    ctx = None
    try:
        ctx, page = init_context(headless=not options.headed)
        
        # Search and download using the new function
        search_and_download(page, params)
        
        input(">>")
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
    finally:
        if ctx is not None:
            logger.info("Closing context...")
            ctx.close()
            logger.info("Context closed.")
