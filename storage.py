"""
Module de gestion du stockage des fichiers (logos, documents) dans Supabase Storage
"""
import streamlit as st
from datetime import datetime
import os


def upload_logo(supabase, logo_file, entreprise_id):
    """
    Upload un logo dans Supabase Storage et retourne l'URL publique
    
    Args:
        supabase: Client Supabase
        logo_file: Fichier uploadé (UploadedFile de Streamlit)
        entreprise_id: ID de l'entreprise
        
    Returns:
        str: URL publique du logo ou None en cas d'erreur
    """
    try:
        # Lire le contenu du fichier
        file_bytes = logo_file.read()
        
        # Générer un nom de fichier unique
        file_extension = logo_file.name.split('.')[-1].lower()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"logo_{entreprise_id}_{timestamp}.{file_extension}"
        
        # Déterminer le content type
        content_type_map = {
            'png': 'image/png',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'gif': 'image/gif',
            'webp': 'image/webp'
        }
        content_type = content_type_map.get(file_extension, 'image/jpeg')
        
        # Upload dans le bucket 'logos'
        # Note: Le bucket 'logos' doit être créé dans Supabase Storage avec accès public
        response = supabase.storage.from_('logos').upload(
            path=file_name,
            file=file_bytes,
            file_options={"content-type": content_type, "upsert": "true"}
        )
        
        # Obtenir l'URL publique
        public_url = supabase.storage.from_('logos').get_public_url(file_name)
        
        return public_url
        
    except Exception as e:
        st.error(f"❌ Erreur lors de l'upload du logo : {str(e)}")
        return None


def delete_logo(supabase, logo_url):
    """
    Supprime un logo du storage Supabase
    
    Args:
        supabase: Client Supabase
        logo_url: URL du logo à supprimer
        
    Returns:
        bool: True si suppression réussie, False sinon
    """
    try:
        # Extraire le nom du fichier de l'URL
        # Format: https://xxxxx.supabase.co/storage/v1/object/public/logos/logo_123_20240101.png
        if '/logos/' in logo_url:
            file_name = logo_url.split('/logos/')[-1]
            
            # Supprimer le fichier
            supabase.storage.from_('logos').remove([file_name])
            return True
        
        return False
        
    except Exception as e:
        st.warning(f"⚠️ Erreur lors de la suppression du logo : {str(e)}")
        return False


def upload_document_projet(supabase, document_file, entreprise_id=None):
    """
    Upload un document de projet dans Supabase Storage
    
    Args:
        supabase: Client Supabase
        document_file: Fichier uploadé (PDF)
        entreprise_id: ID de l'entreprise (optionnel)
        
    Returns:
        str: URL publique du document ou None en cas d'erreur
    """
    try:
        file_bytes = document_file.read()
        
        # Générer un nom de fichier unique
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = f"projet_{entreprise_id}_" if entreprise_id else "projet_"
        file_name = f"{prefix}{timestamp}.pdf"
        
        # Upload dans le bucket 'documents'
        response = supabase.storage.from_('documents').upload(
            path=file_name,
            file=file_bytes,
            file_options={"content-type": "application/pdf", "upsert": "true"}
        )
        
        # Obtenir l'URL publique
        public_url = supabase.storage.from_('documents').get_public_url(file_name)
        
        return public_url
        
    except Exception as e:
        st.warning(f"⚠️ Erreur lors de l'upload du document : {str(e)}")
        return None


def upload_soumission(supabase, document_file, entreprise_id=None):
    """
    Upload un document de soumission dans Supabase Storage
    
    Args:
        supabase: Client Supabase
        document_file: Fichier uploadé (PDF)
        entreprise_id: ID de l'entreprise (optionnel)
        
    Returns:
        str: URL publique du document ou None en cas d'erreur
    """
    try:
        file_bytes = document_file.read()
        
        # Générer un nom de fichier unique
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = f"soumission_{entreprise_id}_" if entreprise_id else "soumission_"
        file_name = f"{prefix}{timestamp}.pdf"
        
        # Upload dans le bucket 'soumissions'
        response = supabase.storage.from_('soumissions').upload(
            path=file_name,
            file=file_bytes,
            file_options={"content-type": "application/pdf", "upsert": "true"}
        )
        
        # Obtenir l'URL publique
        public_url = supabase.storage.from_('soumissions').get_public_url(file_name)
        
        return public_url
        
    except Exception as e:
        st.warning(f"⚠️ Erreur lors de l'upload de la soumission : {str(e)}")
        return None
