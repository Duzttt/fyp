"""
Question Suggestion Service for generating intelligent question suggestions
based on selected documents using a hybrid approach.
"""

import re
import string
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.config import settings


class QuestionSuggestionError(Exception):
    """Custom exception for question suggestion errors."""
    pass


class QuestionSuggestionService:
    """
    Service for generating smart question suggestions based on document content.
    
    Uses a hybrid approach:
    1. Extract keywords and key phrases from documents
    2. Generate candidate questions using templates
    3. Use LLM to optimize and select the best questions
    """
    
    # Question templates by type
    QUESTION_TEMPLATES = {
        "concept": [
            "What is {keyword}?",
            "Explain the concept of {keyword}.",
            "Define {keyword} and its importance.",
            "What does {keyword} mean in this context?",
        ],
        "method": [
            "How does {keyword} work?",
            "What is the process of {keyword}?",
            "Explain how {keyword} is implemented.",
            "What are the steps involved in {keyword}?",
        ],
        "comparison": [
            "What's the difference between {keyword1} and {keyword2}?",
            "Compare {keyword1} with {keyword2}.",
            "How does {keyword1} differ from {keyword2}?",
        ],
        "reason": [
            "Why is {keyword} important?",
            "What are the reasons for using {keyword}?",
            "Why do we need {keyword}?",
        ],
        "example": [
            "Can you give an example of {keyword}?",
            "Show a practical example of {keyword}.",
            "How is {keyword} used in real applications?",
        ],
    }
    
    # Stop words for English
    STOP_WORDS = {
        "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "must", "shall", "can", "need",
        "this", "that", "these", "those", "it", "its", "as", "if", "then",
        "than", "so", "such", "both", "each", "few", "more", "most", "other",
        "some", "any", "no", "nor", "not", "only", "own", "same", "very",
        "just", "also", "now", "here", "there", "when", "where", "why", "how",
        "all", "about", "into", "over", "after", "before", "between", "under",
    }
    
    def __init__(self, llm_provider: str = "local_qwen"):
        """
        Initialize the question suggestion service.
        
        Args:
            llm_provider: LLM provider to use ("local_qwen", "gemini", "openrouter")
        """
        self.llm_provider = llm_provider
        self._http_client: Optional[httpx.Client] = None
    
    def extract_keywords(
        self, 
        text: str, 
        top_k: int = 15,
        min_word_length: int = 3
    ) -> List[Tuple[str, float]]:
        """
        Extract keywords from text using TF-IDF-like scoring.
        
        Args:
            text: Input text to extract keywords from
            top_k: Number of top keywords to return
            min_word_length: Minimum word length to consider
            
        Returns:
            List of (keyword, score) tuples
        """
        if not text or not text.strip():
            return []
        
        # Clean and tokenize
        text = text.lower()
        # Remove punctuation
        text = text.translate(str.maketrans(string.punctuation, " " * len(string.punctuation)))
        words = text.split()
        
        # Filter stop words and short words
        filtered_words = [
            w for w in words 
            if len(w) >= min_word_length and w not in self.STOP_WORDS
        ]
        
        # Count word frequencies
        word_counts = Counter(filtered_words)
        
        # Calculate simple scoring (frequency * word length bonus)
        scored_keywords = []
        for word, count in word_counts.items():
            # Bonus for longer words (often more specific)
            length_bonus = min(1.5, 1 + (len(word) - min_word_length) * 0.1)
            score = count * length_bonus
            scored_keywords.append((word, score))
        
        # Sort by score and return top_k
        scored_keywords.sort(key=lambda x: x[1], reverse=True)
        return scored_keywords[:top_k]
    
    def extract_keyphrases(
        self,
        text: str,
        max_phrase_length: int = 3,
        top_k: int = 10
    ) -> List[Tuple[str, float]]:
        """
        Extract key phrases from text (multi-word expressions).
        
        Args:
            text: Input text
            max_phrase_length: Maximum number of words in a phrase
            top_k: Number of top phrases to return
            
        Returns:
            List of (phrase, score) tuples
        """
        if not text or not text.strip():
            return []
        
        # Extract section headers (look for capitalized phrases or numbered sections)
        headers = self._extract_headers(text)
        
        # Extract noun phrases using simple pattern matching
        phrases = self._extract_noun_phrases(text, max_phrase_length)
        
        # Score phrases (headers get bonus)
        phrase_scores: Dict[str, float] = {}
        for phrase in phrases:
            base_score = len(phrase.split())  # Longer phrases get higher base score
            is_header = any(phrase.lower() in h.lower() for h in headers)
            score = base_score * (2.0 if is_header else 1.0)
            phrase_scores[phrase] = score
        
        # Sort and return top_k
        scored_phrases = sorted(phrase_scores.items(), key=lambda x: x[1], reverse=True)
        return scored_phrases[:top_k]
    
    def _extract_headers(self, text: str) -> List[str]:
        """Extract section headers from text."""
        headers = []
        
        # Pattern for numbered sections (e.g., "1. Introduction", "2.1 Background")
        numbered_pattern = r'^\s*(\d+\.?[\d\.]*\s+[A-Z][^\n]{10,60})'
        numbered_matches = re.findall(numbered_pattern, text, re.MULTILINE)
        headers.extend([m.strip() for m in numbered_matches])
        
        # Pattern for capitalized headers
        cap_pattern = r'^\s*([A-Z][A-Z\s]{3,40})$'
        cap_matches = re.findall(cap_pattern, text, re.MULTILINE)
        headers.extend([m.strip() for m in cap_matches])
        
        return headers
    
    def _extract_noun_phrases(self, text: str, max_length: int = 3) -> List[str]:
        """Extract simple noun phrases from text."""
        phrases = []
        
        # Split into sentences
        sentences = re.split(r'[.!?]', text)
        
        for sentence in sentences:
            words = sentence.split()
            # Look for adjective-noun or noun-noun patterns
            i = 0
            while i < len(words) - 1:
                # Start with a capitalized or significant word
                if len(words[i]) > 3 and words[i].lower() not in self.STOP_WORDS:
                    phrase_words = [words[i]]
                    j = i + 1
                    # Collect consecutive significant words
                    while j < len(words) and j - i < max_length:
                        if len(words[j]) > 2 and words[j].lower() not in self.STOP_WORDS:
                            phrase_words.append(words[j])
                            j += 1
                        else:
                            break
                    
                    if len(phrase_words) >= 2:
                        phrase = " ".join(phrase_words)
                        # Clean the phrase
                        phrase = phrase.strip(string.punctuation)
                        if len(phrase) > 5 and phrase not in phrases:
                            phrases.append(phrase)
                    
                    i = j
                else:
                    i += 1
        
        return phrases
    
    def generate_candidate_questions(
        self,
        keywords: List[Tuple[str, float]],
        keyphrases: List[Tuple[str, float]],
        num_candidates: int = 15
    ) -> List[Dict[str, Any]]:
        """
        Generate candidate questions using templates and extracted keywords.
        
        Args:
            keywords: List of (keyword, score) tuples
            keyphrases: List of (phrase, score) tuples
            num_candidates: Number of candidate questions to generate
            
        Returns:
            List of question dictionaries with type and text
        """
        candidates: List[Dict[str, Any]] = []
        
        # Get top keywords and phrases
        top_keywords = [kw[0] for kw in keywords[:8]]
        top_phrases = [ph[0] for ph in keyphrases[:5]]
        
        # Generate questions from single keywords
        for q_type, templates in self.QUESTION_TEMPLATES.items():
            if q_type == "comparison":
                continue  # Handle separately
            
            for template in templates[:2]:  # Use first 2 templates per type
                for keyword in top_keywords[:5]:
                    # Skip if keyword is too short or common
                    if len(keyword) < 4:
                        continue
                    
                    question = template.format(keyword=keyword)
                    candidates.append({
                        "type": q_type,
                        "text": question,
                        "keywords": [keyword],
                    })
        
        # Generate comparison questions
        comparison_templates = self.QUESTION_TEMPLATES["comparison"]
        for i, kw1 in enumerate(top_keywords[:4]):
            for kw2 in top_keywords[i+1:5]:
                if kw1 != kw2:
                    template = comparison_templates[0]
                    question = template.format(keyword1=kw1, keyword2=kw2)
                    candidates.append({
                        "type": "comparison",
                        "text": question,
                        "keywords": [kw1, kw2],
                    })
        
        # Generate questions from key phrases
        for phrase in top_phrases[:3]:
            template = "Explain the concept of {keyword}."
            question = template.format(keyword=phrase)
            candidates.append({
                "type": "concept",
                "text": question,
                "keywords": [phrase],
            })
        
        # Limit to num_candidates
        return candidates[:num_candidates]
    
    def optimize_questions_with_llm(
        self,
        candidates: List[Dict[str, Any]],
        document_context: str,
        num_final: int = 3
    ) -> List[str]:
        """
        Use LLM to optimize and select the best questions.
        
        Args:
            candidates: List of candidate question dictionaries
            document_context: Context from selected documents
            num_final: Number of final questions to return
            
        Returns:
            List of optimized question strings
        """
        if not candidates:
            return []
        
        # Prepare candidate questions list
        candidate_texts = [c["text"] for c in candidates]
        
        # Build prompt for LLM
        prompt = self._build_optimization_prompt(
            candidate_texts, 
            document_context,
            num_final
        )
        
        try:
            if self.llm_provider == "local_qwen":
                response = self._call_local_qwen(prompt)
            elif self.llm_provider == "gemini":
                response = self._call_gemini(prompt)
            elif self.llm_provider == "openrouter":
                response = self._call_openrouter(prompt)
            else:
                # Fallback to template-based selection
                return self._select_diverse_questions(candidates, num_final)
            
            # Parse LLM response
            questions = self._parse_llm_response(response, num_final)
            
            if questions:
                return questions
            
        except Exception as e:
            # Fallback to template-based selection
            print(f"LLM optimization failed: {e}")
        
        # Fallback: select diverse questions without LLM
        return self._select_diverse_questions(candidates, num_final)
    
    def _build_optimization_prompt(
        self,
        candidates: List[str],
        context: str,
        num_final: int
    ) -> str:
        """Build the prompt for LLM optimization."""
        candidates_str = "\n".join([f"{i+1}. {q}" for i, q in enumerate(candidates[:10])])
        
        context_preview = context[:1000] + "..." if len(context) > 1000 else context
        
        prompt = f"""You are helping generate good question suggestions for a lecture note Q&A system.

Based on the following lecture content, select EXACTLY {num_final} diverse and high-quality questions from the candidate list.

Requirements:
1. Questions should be diverse (different types: definition, process, comparison, example)
2. Questions should be directly relevant to the lecture content
3. Questions should be clear and concise (under 15 words each)
4. Avoid similar or duplicate questions
5. Prioritize questions about key concepts

Lecture Content:
{context_preview}

Candidate Questions:
{candidates_str}

Respond with ONLY the numbers of your selected questions (one per line), like:
1
3
5

Or if you want to slightly modify a question, respond with the modified version:
Modified: What is the difference between X and Y?
"""
        return prompt
    
    def _call_local_qwen(self, prompt: str) -> str:
        """Call local Qwen model via Ollama."""
        try:
            from ollama import Client as OllamaClient
            
            client = OllamaClient(
                host=settings.LOCAL_QWEN_BASE_URL,
                timeout=settings.LOCAL_QWEN_TIMEOUT_SECONDS,
            )
            
            model_response = client.chat(
                model=settings.LOCAL_QWEN_MODEL,
                messages=[{"role": "user", "content": prompt}],
                stream=False,
                keep_alive=settings.LOCAL_QWEN_KEEP_ALIVE,
            )
            
            return str(model_response.get("message", {}).get("content", "")).strip()
            
        except Exception as e:
            raise QuestionSuggestionError(f"Local Qwen call failed: {e}")
    
    def _call_gemini(self, prompt: str) -> str:
        """Call Gemini API."""
        headers = {"Content-Type": "application/json"}
        
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": 200,
                "temperature": 0.3,
            }
        }
        
        try:
            url = f"{settings.GEMINI_BASE_URL}/models/{settings.GEMINI_MODEL}:generateContent?key={settings.GEMINI_API_KEY}"
            response = httpx.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if "candidates" in data and len(data["candidates"]) > 0:
                return data["candidates"][0]["content"]["parts"][0]["text"].strip()
            
            raise QuestionSuggestionError("Invalid Gemini response format")
            
        except Exception as e:
            raise QuestionSuggestionError(f"Gemini call failed: {e}")
    
    def _call_openrouter(self, prompt: str) -> str:
        """Call OpenRouter API."""
        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": "anthropic/claude-3-haiku",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 200,
        }
        
        try:
            response = httpx.post(
                f"{settings.OPENROUTER_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
            
        except Exception as e:
            raise QuestionSuggestionError(f"OpenRouter call failed: {e}")
    
    def _parse_llm_response(self, response: str, num_final: int) -> List[str]:
        """Parse LLM response to extract selected questions."""
        questions = []
        
        for line in response.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            
            # Check for modified questions
            if line.lower().startswith("modified:"):
                question = line[9:].strip()
                if question and question not in questions:
                    questions.append(question)
                continue
            
            # Check for number selection
            if line.isdigit():
                # This would need the original candidates to map back
                # For simplicity, skip in this implementation
                continue
            
            # Treat as a question directly
            if line.endswith("?") and len(line) < 100:
                if line not in questions:
                    questions.append(line)
        
        return questions[:num_final]
    
    def _select_diverse_questions(
        self,
        candidates: List[Dict[str, Any]],
        num_final: int
    ) -> List[str]:
        """
        Select diverse questions without LLM (fallback method).
        
        Prioritizes:
        1. Different question types
        2. Higher-scored keywords
        3. Questions under 15 words
        """
        selected: List[str] = []
        selected_types: set = set()
        
        # Group candidates by type
        by_type: Dict[str, List[Dict[str, Any]]] = {}
        for candidate in candidates:
            q_type = candidate["type"]
            if q_type not in by_type:
                by_type[q_type] = []
            by_type[q_type].append(candidate)
        
        # Prioritize order of question types
        type_priority = ["concept", "method", "comparison", "reason", "example"]
        
        # Select one question per type until we have enough
        for q_type in type_priority:
            if len(selected) >= num_final:
                break
            
            if q_type not in by_type:
                continue
            
            # Sort candidates by keyword score (approximated by position)
            type_candidates = by_type[q_type]
            
            for candidate in type_candidates:
                question = candidate["text"]
                
                # Skip if too long
                if len(question.split()) > 15:
                    continue
                
                # Skip if similar to already selected
                if self._is_similar_to_selected(question, selected):
                    continue
                
                selected.append(question)
                selected_types.add(q_type)
                break
        
        # If still need more, add from any type
        if len(selected) < num_final:
            for candidate in candidates:
                if len(selected) >= num_final:
                    break
                
                question = candidate["text"]
                if len(question.split()) <= 15 and question not in selected:
                    selected.append(question)
        
        return selected[:num_final]
    
    def _is_similar_to_selected(self, question: str, selected: List[str], threshold: float = 0.6) -> bool:
        """Check if a question is too similar to already selected questions."""
        question_words = set(question.lower().split())
        
        for sel_question in selected:
            sel_words = set(sel_question.lower().split())
            
            # Simple Jaccard similarity
            if question_words and sel_words:
                intersection = len(question_words & sel_words)
                union = len(question_words | sel_words)
                similarity = intersection / union if union > 0 else 0
                
                if similarity > threshold:
                    return True
        
        return False
    
    def generate_suggestions(
        self,
        documents: List[Dict[str, Any]],
        num_suggestions: int = 3
    ) -> Dict[str, Any]:
        """
        Main method to generate question suggestions for selected documents.
        
        Args:
            documents: List of document dictionaries with 'name', 'content', 'chunks'
            num_suggestions: Number of suggestions to generate
            
        Returns:
            Dictionary with 'suggestions' list and 'generated_from' document names
        """
        if not documents:
            return {"suggestions": [], "generated_from": []}
        
        # Combine document content
        all_text = []
        doc_names = []
        
        for doc in documents:
            doc_name = doc.get("name") or doc.get("filename", "Unknown")
            doc_names.append(doc_name)
            
            # Combine content from chunks or direct content
            content = doc.get("content", "")
            chunks = doc.get("chunks", [])
            
            if chunks:
                chunk_texts = [c.get("text", "") for c in chunks[:10]]  # Limit chunks
                content = "\n".join(chunk_texts)
            
            if content:
                all_text.append(f"=== {doc_name} ===\n{content}")
        
        combined_text = "\n\n".join(all_text)
        
        if not combined_text.strip():
            return {"suggestions": [], "generated_from": doc_names}
        
        # Step 1: Extract keywords
        keywords = self.extract_keywords(combined_text, top_k=15)
        
        # Step 2: Extract key phrases
        keyphrases = self.extract_keyphrases(combined_text, top_k=10)
        
        # Step 3: Generate candidate questions
        candidates = self.generate_candidate_questions(keywords, keyphrases, num_candidates=15)
        
        # Step 4: Optimize and select final questions
        final_questions = self.optimize_questions_with_llm(
            candidates, 
            combined_text, 
            num_final=num_suggestions
        )
        
        return {
            "suggestions": final_questions,
            "generated_from": doc_names,
        }


# Singleton instance for reuse
_service_instance: Optional[QuestionSuggestionService] = None


def get_question_suggestion_service(
    llm_provider: str = "local_qwen"
) -> QuestionSuggestionService:
    """Get or create the question suggestion service instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = QuestionSuggestionService(llm_provider)
    return _service_instance


def generate_question_suggestions(
    documents: List[Dict[str, Any]],
    num_suggestions: int = 3
) -> Dict[str, Any]:
    """
    Convenience function to generate question suggestions.
    
    Args:
        documents: List of document dictionaries
        num_suggestions: Number of suggestions to generate
        
    Returns:
        Dictionary with suggestions list and source documents
    """
    service = get_question_suggestion_service()
    return service.generate_suggestions(documents, num_suggestions)
