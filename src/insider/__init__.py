"""Insider Trading Tracker Module.

Track insider transactions, detect cluster buying, and monitor institutional holdings.

Example:
    from src.insider import (
        TransactionTracker, InsiderTransaction, InsiderType, TransactionType,
        ClusterDetector, InstitutionalTracker,
        SignalGenerator, AlertManager,
    )
    
    # Create tracker and add transactions
    tracker = TransactionTracker()
    tracker.add_transaction(InsiderTransaction(
        symbol="AAPL",
        insider_name="Tim Cook",
        insider_type=InsiderType.CEO,
        transaction_type=TransactionType.BUY,
        shares=50000,
        price=185.0,
    ))
    
    # Detect clusters
    detector = ClusterDetector(tracker)
    clusters = detector.detect_clusters()
    
    # Generate signals
    generator = SignalGenerator(tracker, detector)
    signals = generator.generate_signals()
"""

from src.insider.config import (
    InsiderType,
    TransactionType,
    SignalStrength,
    InstitutionType,
    FilingType,
    TRANSACTION_CODES,
    BULLISH_TRANSACTIONS,
    BEARISH_TRANSACTIONS,
    LARGE_BUY_THRESHOLD,
    SIGNIFICANT_BUY_THRESHOLD,
    InsiderConfig,
    InstitutionalConfig,
    DEFAULT_INSIDER_CONFIG,
    DEFAULT_INSTITUTIONAL_CONFIG,
)

from src.insider.models import (
    InsiderTransaction,
    InsiderSummary,
    InsiderCluster,
    InstitutionalHolding,
    InstitutionalSummary,
    InsiderProfile,
    InsiderSignal,
    InsiderAlert,
)

from src.insider.transactions import (
    TransactionTracker,
    generate_sample_transactions,
)

from src.insider.clusters import ClusterDetector

from src.insider.institutions import (
    InstitutionalTracker,
    generate_sample_institutional,
)

from src.insider.profiles import ProfileManager

from src.insider.signals import (
    SignalGenerator,
    AlertManager,
    create_default_alerts,
)


__all__ = [
    # Config
    "InsiderType",
    "TransactionType",
    "SignalStrength",
    "InstitutionType",
    "FilingType",
    "TRANSACTION_CODES",
    "BULLISH_TRANSACTIONS",
    "BEARISH_TRANSACTIONS",
    "LARGE_BUY_THRESHOLD",
    "SIGNIFICANT_BUY_THRESHOLD",
    "InsiderConfig",
    "InstitutionalConfig",
    "DEFAULT_INSIDER_CONFIG",
    "DEFAULT_INSTITUTIONAL_CONFIG",
    # Models
    "InsiderTransaction",
    "InsiderSummary",
    "InsiderCluster",
    "InstitutionalHolding",
    "InstitutionalSummary",
    "InsiderProfile",
    "InsiderSignal",
    "InsiderAlert",
    # Transactions
    "TransactionTracker",
    "generate_sample_transactions",
    # Clusters
    "ClusterDetector",
    # Institutions
    "InstitutionalTracker",
    "generate_sample_institutional",
    # Profiles
    "ProfileManager",
    # Signals
    "SignalGenerator",
    "AlertManager",
    "create_default_alerts",
]
