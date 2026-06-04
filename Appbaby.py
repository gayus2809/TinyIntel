import streamlit as st
import requests
import xml.etree.ElementTree as ET  # Added this line to fix the error
# --- CONFIGURATION ---
# Safely fetches the key from Streamlit's secure dashboard settings
HF_API_KEY = st.secrets["HF_API_KEY"]
HF_API_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-cnn"
# --- HELPER FUNCTIONS ---
def search_pubmed(query, max_results=3):
    """Searches PubMed for free full-text articles matching the query."""
    search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    search_params = {
        "db": "pubmed",
        "term": f"{query} AND free full text[sb]",
        "retmode": "json",
        "retmax": max_results
    }
    response = requests.get(search_url, params=search_params)
    if response.status_code == 200:
        return response.json().get("esearchresult", {}).get("idlist", [])
    return []

def fetch_abstracts(id_list):
    """Fetches the title and abstract for a list of PubMed IDs via XML."""
    if not id_list:
        return []
        
    fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    fetch_params = {
        "db": "pubmed",
        "id": ",".join(id_list),
        "retmode": "xml"
    }
    
    response = requests.get(fetch_url, params=fetch_params)
    papers = []
    
    if response.status_code == 200:
        root = ET.fromstring(response.content)
        for article in root.findall('.//PubmedArticle'):
            title = article.findtext('.//ArticleTitle')
            # Sometimes abstracts are split into multiple sections (Background, Methods, etc.)
            abstract_texts = article.findall('.//AbstractText')
            abstract = " ".join([elem.text for elem in abstract_texts if elem.text])
            
            if title and abstract:
                papers.append({"title": title, "abstract": abstract})
                
    return papers

def summarize_text(text):
    """Sends text to Hugging Face's BART model for summarization."""
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    payload = {
        "inputs": text, 
        "parameters": {"max_length": 150, "min_length": 40, "do_sample": False}
    }
    
    response = requests.post(HF_API_URL, headers=headers, json=payload)
    
    if response.status_code == 200:
        return response.json()[0]['summary_text']
    elif response.status_code == 503:
        # Free HF models go to sleep when inactive. 503 means it's booting up.
        return "⏳ The AI model is warming up. Please wait 20 seconds and click search again."
    else:
        return f"⚠️ Error {response.status_code}: Could not summarize."
        def summarize_text(text):
    payload = {
        "inputs": text,
        "parameters": {"max_length": 150, "min_length": 40, "do_sample": False}
    }
    
    try:
        response = requests.post(HF_API_URL, headers=headers, json=payload, timeout=10)
        if response.status_code == 200:
            return response.json()[0]['summary_text']
        else:
            return f"Error: Inference API returned status code {response.status_code}"
            
    except requests.exceptions.ConnectionError:
        return "The AI summarization service is currently unreachable. Please try again in a few moments."
    except Exception as e:
        return f"An unexpected error occurred during summarization: {str(e)}"

# --- STREAMLIT UI ---
st.set_page_config(page_title="Baby Product Scientific Lookup ", page_icon="👶")

st.title("👶 Baby Product Research")
st.write("Enter a baby product, ingredient, or brand (e.g., *talcum powder*, *melatonin*, *baby walker*). This app will search PubMed for open-access medical literature and summarize the findings.")

st.markdown("---")

product_name = st.text_input("**Enter a baby product or topic:**", placeholder="e.g., pacifiers")

if st.button("Search & Summarize", type="primary"):
    if not product_name.strip():
        st.warning("Please enter a product name to search.")
    else:
        with st.spinner(f"Searching PubMed for '{product_name}'..."):
            paper_ids = search_pubmed(product_name, max_results=3)
            
        if not paper_ids:
            st.error(f"No free open-access papers found for '{product_name}'. Try broadening your search terms.")
        else:
            with st.spinner("Fetching and summarizing abstracts..."):
                papers = fetch_abstracts(paper_ids)
                
                if not papers:
                    st.warning("Found papers, but they didn't have usable abstracts.")
                else:
                    for i, paper in enumerate(papers):
                        st.subheader(f"Paper {i+1}: {paper['title']}")
                        
                        summary = summarize_text(paper['abstract'])
                        
                        st.info(f"**AI Summary:** {summary}")
                        with st.expander("Read Original Abstract"):
                            st.write(paper['abstract'])
                        st.markdown("---")
