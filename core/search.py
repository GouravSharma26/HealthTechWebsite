import json
import logging
from django.conf import settings
from django.db import connection
from django.db.models import Q
from .models import DoctorProfile

logger = logging.getLogger(__name__)

# Lazy-load the model to avoid slow startup and memory usage if not used
_model = None

def get_model():
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            # Using a very small and fast model ideal for this use case
            _model = SentenceTransformer('all-MiniLM-L6-v2')
        except Exception as e:
            logger.error(f"Failed to load sentence-transformers model: {e}")
            return None
    return _model

def generate_doctor_embedding(doctor_profile):
    """
    Generates an embedding vector for a given doctor profile based on their
    specialization, experience, and about text.
    """
    model = get_model()
    if not model:
        return None
        
    text = f"{doctor_profile.specialization}. {doctor_profile.about or ''}. {doctor_profile.qualifications or ''}"
    
    try:
        embedding = model.encode(text)
        # Convert numpy array to list for JSON serialization
        return embedding.tolist()
    except Exception as e:
        logger.error(f"Failed to generate embedding for doctor {doctor_profile.id}: {e}")
        return None

def update_doctor_embedding(doctor_profile):
    """
    Updates the search_embedding field on the doctor profile and saves it.
    """
    embedding_list = generate_doctor_embedding(doctor_profile)
    if embedding_list is not None:
        doctor_profile.search_embedding = embedding_list
        # Using update to avoid triggering signals recursively if called from a post_save signal
        DoctorProfile.objects.filter(id=doctor_profile.id).update(search_embedding=embedding_list)

def text_search_doctors(query, top_k=20):
    """Plain substring search on username / specialization (used as the fallback)."""
    qs = DoctorProfile.objects.filter(
        Q(user__username__icontains=query) | Q(specialization__icontains=query)
    ).select_related('user').distinct()
    return list(qs[:top_k])

def update_doctor_embedding_in_thread(doctor_id):
    """Thread target: own DB connection, always closed (threads don't get request cleanup)."""
    try:
        doctor = DoctorProfile.objects.filter(id=doctor_id).first()
        if doctor:
            update_doctor_embedding(doctor)
    finally:
        connection.close()

def search_doctors(query, top_k=5):
    """
    Given a natural language query, searches the database for the most relevant doctors.
    Falls back to plain text matching when the embedding model is unavailable
    (e.g. sentence-transformers not installed) or no doctor has an embedding yet.
    """
    model = get_model()
    if not model:
        return text_search_doctors(query, top_k)
        
    try:
        from sentence_transformers import util
        import torch
    except ImportError:
        return text_search_doctors(query, top_k)

    query_embedding = model.encode(query, convert_to_tensor=True)
    
    # Load all doctors that have an embedding
    doctors = list(DoctorProfile.objects.exclude(search_embedding__isnull=True).select_related('user'))
    if not doctors:
        return text_search_doctors(query, top_k)
        
    # Convert stored JSON arrays back to tensors
    doctor_embeddings = [d.search_embedding for d in doctors]
    corpus_embeddings = torch.tensor(doctor_embeddings)
    
    # Compute cosine similarities
    cos_scores = util.cos_sim(query_embedding, corpus_embeddings)[0]
    
    # Get top_k results
    top_results = torch.topk(cos_scores, k=min(top_k, len(doctors)))
    
    # Extract the matching doctor profiles
    matched_doctors = []
    # top_results[1] contains indices
    for idx in top_results[1]:
        matched_doctors.append(doctors[idx])
        
    return matched_doctors
