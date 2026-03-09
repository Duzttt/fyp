"""
Django models for the Lecture Note Q&A System.
"""

from django.db import models


class SuggestedQuestion(models.Model):
    """
    Model to store generated question suggestions and track their usage.
    
    This model stores questions that were suggested to users based on
    selected documents, along with statistics about their usage.
    """
    
    # Question types
    QUESTION_TYPE_CHOICES = [
        ("concept", "Concept/Definition"),
        ("method", "Method/Process"),
        ("comparison", "Comparison"),
        ("reason", "Reason/Explanation"),
        ("example", "Example/Application"),
    ]
    
    # The question text
    question_text = models.TextField(
        help_text="The suggested question text"
    )
    
    # Question type/category
    question_type = models.CharField(
        max_length=20,
        choices=QUESTION_TYPE_CHOICES,
        default="concept",
        help_text="Type of question (concept, method, comparison, etc.)"
    )
    
    # Associated notebook (if using notebooks feature)
    notebook = models.ForeignKey(
        "Notebook",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="suggested_questions",
        help_text="Associated notebook (optional)"
    )
    
    # Documents this suggestion was generated from
    # Using a text field to store document names/IDs as comma-separated values
    # This is simpler than a M2M for this use case
    document_names = models.TextField(
        help_text="Comma-separated list of document names this was generated from"
    )
    
    # Tracking statistics
    click_count = models.IntegerField(
        default=0,
        help_text="Number of times this suggestion was clicked"
    )
    
    feedback_score = models.FloatField(
        null=True,
        blank=True,
        help_text="User feedback score (if collected)"
    )
    
    # Metadata about generation
    generation_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata about question generation"
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this suggestion was created"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When this suggestion was last updated"
    )
    
    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["question_type"]),
            models.Index(fields=["click_count"]),
        ]
    
    def __str__(self) -> str:
        return f"{self.question_type}: {self.question_text[:50]}..."
    
    def increment_click_count(self) -> None:
        """Increment the click count and save."""
        self.click_count += 1
        self.save(update_fields=["click_count", "updated_at"])
    
    def set_feedback(self, score: float) -> None:
        """Set user feedback score."""
        self.feedback_score = score
        self.save(update_fields=["feedback_score", "updated_at"])


class Notebook(models.Model):
    """
    Model to represent a collection/notebook of documents.
    
    This is a simple notebook model that can be used to group
    documents together for organized Q&A sessions.
    """
    
    name = models.CharField(
        max_length=255,
        unique=True,
        help_text="Name of the notebook"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Description of the notebook"
    )
    
    # Store document names as comma-separated values
    document_names = models.TextField(
        default="",
        blank=True,
        help_text="Comma-separated list of document names in this notebook"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ["-created_at"]
    
    def __str__(self) -> str:
        return self.name
    
    def get_documents(self) -> list:
        """Get list of document names."""
        if not self.document_names:
            return []
        return [name.strip() for name in self.document_names.split(",") if name.strip()]
    
    def add_document(self, document_name: str) -> None:
        """Add a document to the notebook."""
        docs = self.get_documents()
        if document_name not in docs:
            docs.append(document_name)
            self.document_names = ", ".join(docs)
            self.save(update_fields=["document_names", "updated_at"])
    
    def remove_document(self, document_name: str) -> None:
        """Remove a document from the notebook."""
        docs = self.get_documents()
        if document_name in docs:
            docs.remove(document_name)
            self.document_names = ", ".join(docs)
            self.save(update_fields=["document_names", "updated_at"])
