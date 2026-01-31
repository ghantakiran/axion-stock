"""Watchlist Notes and Tags.

Notes and tagging system for watchlist items.
"""

from datetime import datetime, timezone
from typing import Optional
import logging

from src.watchlist.config import NoteType
from src.watchlist.models import WatchlistNote, Tag

logger = logging.getLogger(__name__)


class NotesManager:
    """Manages notes and tags for watchlist items.
    
    Provides CRUD for notes and tag management.
    
    Example:
        manager = NotesManager()
        
        # Add a note
        note = manager.add_note(
            watchlist_id="wl1",
            symbol="AAPL",
            title="Earnings Analysis",
            content="Strong Q4 results...",
            note_type=NoteType.EARNINGS,
        )
        
        # Add tags
        manager.create_tag("growth", color="#2ecc71")
        manager.add_tag_to_note(note.note_id, "growth")
    """
    
    def __init__(self):
        self._notes: dict[str, WatchlistNote] = {}
        self._tags: dict[str, Tag] = {}
    
    # =========================================================================
    # Notes CRUD
    # =========================================================================
    
    def add_note(
        self,
        watchlist_id: str,
        symbol: str,
        title: str,
        content: str,
        note_type: NoteType = NoteType.GENERAL,
        tags: Optional[list[str]] = None,
        created_by: str = "user",
    ) -> WatchlistNote:
        """Add a new note.
        
        Args:
            watchlist_id: Parent watchlist ID.
            symbol: Stock symbol.
            title: Note title.
            content: Note content.
            note_type: Type of note.
            tags: Optional tags.
            created_by: User who created it.
            
        Returns:
            Created WatchlistNote.
        """
        note = WatchlistNote(
            watchlist_id=watchlist_id,
            symbol=symbol.upper(),
            title=title,
            content=content,
            note_type=note_type,
            tags=tags or [],
            created_by=created_by,
        )
        
        self._notes[note.note_id] = note
        
        # Update tag usage counts
        for tag_name in note.tags:
            self._increment_tag_usage(tag_name)
        
        return note
    
    def get_note(self, note_id: str) -> Optional[WatchlistNote]:
        """Get note by ID."""
        return self._notes.get(note_id)
    
    def get_notes_for_symbol(
        self,
        symbol: str,
        watchlist_id: Optional[str] = None,
    ) -> list[WatchlistNote]:
        """Get all notes for a symbol.
        
        Args:
            symbol: Stock symbol.
            watchlist_id: Optional filter to specific watchlist.
            
        Returns:
            List of notes sorted by created_at (newest first).
        """
        notes = [
            n for n in self._notes.values()
            if n.symbol == symbol.upper()
        ]
        
        if watchlist_id:
            notes = [n for n in notes if n.watchlist_id == watchlist_id]
        
        return sorted(notes, key=lambda n: n.created_at, reverse=True)
    
    def get_notes_for_watchlist(self, watchlist_id: str) -> list[WatchlistNote]:
        """Get all notes for a watchlist."""
        notes = [n for n in self._notes.values() if n.watchlist_id == watchlist_id]
        return sorted(notes, key=lambda n: n.created_at, reverse=True)
    
    def update_note(
        self,
        note_id: str,
        title: Optional[str] = None,
        content: Optional[str] = None,
        note_type: Optional[NoteType] = None,
    ) -> Optional[WatchlistNote]:
        """Update a note."""
        note = self._notes.get(note_id)
        if not note:
            return None
        
        if title is not None:
            note.title = title
        if content is not None:
            note.content = content
        if note_type is not None:
            note.note_type = note_type
        
        note.updated_at = datetime.now(timezone.utc)
        return note
    
    def delete_note(self, note_id: str) -> bool:
        """Delete a note."""
        note = self._notes.get(note_id)
        if note:
            # Decrement tag usage
            for tag_name in note.tags:
                self._decrement_tag_usage(tag_name)
            
            del self._notes[note_id]
            return True
        return False
    
    def search_notes(
        self,
        query: str,
        note_type: Optional[NoteType] = None,
    ) -> list[WatchlistNote]:
        """Search notes by content.
        
        Args:
            query: Search query.
            note_type: Optional filter by type.
            
        Returns:
            List of matching notes.
        """
        query = query.lower()
        results = []
        
        for note in self._notes.values():
            if note_type and note.note_type != note_type:
                continue
            
            if (query in note.title.lower() or
                query in note.content.lower() or
                query in note.symbol.lower()):
                results.append(note)
        
        return sorted(results, key=lambda n: n.created_at, reverse=True)
    
    # =========================================================================
    # Tags CRUD
    # =========================================================================
    
    def create_tag(
        self,
        name: str,
        color: str = "#3498db",
    ) -> Tag:
        """Create a new tag.
        
        Args:
            name: Tag name.
            color: Display color.
            
        Returns:
            Created Tag.
        """
        # Normalize name
        name = name.lower().strip()
        
        # Check if exists
        if name in self._tags:
            return self._tags[name]
        
        tag = Tag(name=name, color=color)
        self._tags[name] = tag
        return tag
    
    def get_tag(self, name: str) -> Optional[Tag]:
        """Get tag by name."""
        return self._tags.get(name.lower())
    
    def get_all_tags(self) -> list[Tag]:
        """Get all tags sorted by usage."""
        return sorted(self._tags.values(), key=lambda t: t.usage_count, reverse=True)
    
    def update_tag(
        self,
        name: str,
        new_name: Optional[str] = None,
        color: Optional[str] = None,
    ) -> Optional[Tag]:
        """Update a tag."""
        tag = self._tags.get(name.lower())
        if not tag:
            return None
        
        if new_name:
            # Rename tag
            del self._tags[name.lower()]
            tag.name = new_name.lower()
            self._tags[new_name.lower()] = tag
            
            # Update notes
            for note in self._notes.values():
                if name.lower() in [t.lower() for t in note.tags]:
                    note.tags = [new_name if t.lower() == name.lower() else t for t in note.tags]
        
        if color:
            tag.color = color
        
        return tag
    
    def delete_tag(self, name: str) -> bool:
        """Delete a tag (removes from all notes too)."""
        name = name.lower()
        if name not in self._tags:
            return False
        
        # Remove from all notes
        for note in self._notes.values():
            note.tags = [t for t in note.tags if t.lower() != name]
        
        del self._tags[name]
        return True
    
    def _increment_tag_usage(self, tag_name: str) -> None:
        """Increment tag usage count."""
        tag = self._tags.get(tag_name.lower())
        if tag:
            tag.usage_count += 1
        else:
            # Auto-create tag
            self.create_tag(tag_name)
            self._tags[tag_name.lower()].usage_count = 1
    
    def _decrement_tag_usage(self, tag_name: str) -> None:
        """Decrement tag usage count."""
        tag = self._tags.get(tag_name.lower())
        if tag and tag.usage_count > 0:
            tag.usage_count -= 1
    
    # =========================================================================
    # Note Tags
    # =========================================================================
    
    def add_tag_to_note(self, note_id: str, tag_name: str) -> bool:
        """Add a tag to a note."""
        note = self._notes.get(note_id)
        if not note:
            return False
        
        tag_name = tag_name.lower()
        if tag_name not in [t.lower() for t in note.tags]:
            note.tags.append(tag_name)
            note.updated_at = datetime.now(timezone.utc)
            self._increment_tag_usage(tag_name)
            return True
        return False
    
    def remove_tag_from_note(self, note_id: str, tag_name: str) -> bool:
        """Remove a tag from a note."""
        note = self._notes.get(note_id)
        if not note:
            return False
        
        tag_name = tag_name.lower()
        original_len = len(note.tags)
        note.tags = [t for t in note.tags if t.lower() != tag_name]
        
        if len(note.tags) < original_len:
            note.updated_at = datetime.now(timezone.utc)
            self._decrement_tag_usage(tag_name)
            return True
        return False
    
    def get_notes_by_tag(self, tag_name: str) -> list[WatchlistNote]:
        """Get all notes with a specific tag."""
        tag_name = tag_name.lower()
        return [
            n for n in self._notes.values()
            if tag_name in [t.lower() for t in n.tags]
        ]
    
    def suggest_tags(self, partial: str, limit: int = 10) -> list[str]:
        """Suggest tags based on partial input.
        
        Args:
            partial: Partial tag name.
            limit: Maximum suggestions.
            
        Returns:
            List of suggested tag names.
        """
        partial = partial.lower()
        matches = [
            tag.name for tag in self._tags.values()
            if tag.name.startswith(partial)
        ]
        
        # Sort by usage
        matches.sort(key=lambda n: self._tags[n].usage_count, reverse=True)
        return matches[:limit]
