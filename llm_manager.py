"""
Gestion des fournisseurs LLM (Gemini, Groq)
"""
import streamlit as st
import google.generativeai as genai
import requests
import config


class LLMManager:
    def __init__(self):
        self.providers = []
        self._init_providers()
    
    def _init_providers(self):
        """Initialise les fournisseurs LLM avec Gemini en priorité"""
        if config.GEMINI_API_KEY:
            try:
                genai.configure(api_key=config.GEMINI_API_KEY)
                model = genai.GenerativeModel('gemini-2.0-flash-exp')
                self.providers.append({
                    "name": "Gemini 2.0 Flash",
                    "client": model,
                    "type": "gemini"
                })
            except Exception as e:
                st.warning(f"⚠️ Gemini non disponible : {str(e)[:100]}")
        
        if config.GROQ_API_KEY:
            self.providers.append({
                "name": "Groq LLaMA 3.3 70B",
                "api_key": config.GROQ_API_KEY,
                "type": "groq"
            })
        
        if not self.providers:
            st.error("❌ Aucun LLM configuré ! Ajoutez GEMINI_API_KEY ou GROQ_API_KEY dans .env")
            st.stop()
    
    def analyze(self, prompt: str, max_tokens: int = 2000) -> dict:
        """Analyse un prompt avec fallback automatique entre les LLMs"""
        last_error = None
        
        for provider in self.providers:
            try:
                if provider["type"] == "groq":
                    response = requests.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {provider['api_key']}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": "llama-3.3-70b-versatile",
                            "messages": [{"role": "user", "content": prompt}],
                            "max_tokens": max_tokens,
                            "temperature": 0.3
                        },
                        timeout=30
                    )
                    response.raise_for_status()
                    return {
                        "success": True,
                        "result": response.json()["choices"][0]["message"]["content"],
                        "provider": provider["name"],
                        "error": None
                    }
                elif provider["type"] == "gemini":
                    response = provider["client"].generate_content(
                        prompt,
                        generation_config={"max_output_tokens": max_tokens, "temperature": 0.3}
                    )
                    return {
                        "success": True,
                        "result": response.text,
                        "provider": provider["name"],
                        "error": None
                    }
            except requests.exceptions.Timeout:
                last_error = f"Le service {provider['name']} a mis trop de temps à répondre"
                continue
            except requests.exceptions.ConnectionError:
                last_error = f"Impossible de se connecter au service {provider['name']}"
                continue
            except Exception as e:
                last_error = f"Erreur avec {provider['name']}: {str(e)[:100]}"
                continue
        
        return {
            "success": False,
            "result": None,
            "provider": None,
            "error": last_error or "Tous les services d'IA sont indisponibles. Veuillez réessayer plus tard."
        }
