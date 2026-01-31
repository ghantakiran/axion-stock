"""Tests for Broker Integrations."""

import pytest
from datetime import datetime, timezone

from src.brokers import (
    # Config
    BrokerType, OrderSide, OrderType, OrderStatus, TimeInForce,
    BROKER_CAPABILITIES,
    # Models
    BrokerAccount, AccountBalances, Position, Order,
    OrderRequest, OrderResult, Quote,
    # Credentials
    BrokerCredentials, CredentialManager, OAuthManager,
    # Manager
    BrokerManager,
    # Factory
    create_broker,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def alpaca_credentials():
    """Sample Alpaca credentials."""
    return {
        "api_key": "test_api_key",
        "api_secret": "test_api_secret",
    }


@pytest.fixture
def order_request():
    """Sample order request."""
    return OrderRequest(
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=10,
        order_type=OrderType.MARKET,
        time_in_force=TimeInForce.DAY,
    )


# =============================================================================
# Test Broker Capabilities
# =============================================================================

class TestBrokerCapabilities:
    """Tests for broker capabilities."""
    
    def test_alpaca_capabilities(self):
        """Test Alpaca capabilities."""
        caps = BROKER_CAPABILITIES[BrokerType.ALPACA]
        assert caps.stocks is True
        assert caps.options is False
        assert caps.crypto is True
        assert caps.fractional_shares is True
    
    def test_schwab_capabilities(self):
        """Test Schwab capabilities."""
        caps = BROKER_CAPABILITIES[BrokerType.SCHWAB]
        assert caps.stocks is True
        assert caps.options is True
        assert caps.mutual_funds is True
    
    def test_ibkr_capabilities(self):
        """Test IBKR capabilities."""
        caps = BROKER_CAPABILITIES[BrokerType.IBKR]
        assert caps.stocks is True
        assert caps.options is True
        assert caps.futures is True
        assert caps.forex is True


# =============================================================================
# Test Credential Manager
# =============================================================================

class TestCredentialManager:
    """Tests for CredentialManager."""
    
    def test_store_and_retrieve(self):
        """Test storing and retrieving credentials."""
        manager = CredentialManager()
        
        creds = BrokerCredentials(
            broker=BrokerType.ALPACA,
            account_id="test123",
            api_key="my_api_key",
            api_secret="my_secret",
        )
        
        manager.store_credentials(creds)
        retrieved = manager.get_credentials(BrokerType.ALPACA, "test123")
        
        assert retrieved is not None
        assert retrieved.api_key == "my_api_key"
    
    def test_update_tokens(self):
        """Test updating tokens."""
        manager = CredentialManager()
        
        creds = BrokerCredentials(
            broker=BrokerType.SCHWAB,
            account_id="schwab123",
            access_token="old_token",
        )
        manager.store_credentials(creds)
        
        success = manager.update_tokens(
            BrokerType.SCHWAB,
            "schwab123",
            "new_token",
            expires_in=3600,
        )
        
        assert success is True
        updated = manager.get_credentials(BrokerType.SCHWAB, "schwab123")
        assert updated.access_token == "new_token"
    
    def test_delete_credentials(self):
        """Test deleting credentials."""
        manager = CredentialManager()
        
        creds = BrokerCredentials(
            broker=BrokerType.TRADIER,
            account_id="tradier123",
        )
        manager.store_credentials(creds)
        
        assert manager.delete_credentials(BrokerType.TRADIER, "tradier123") is True
        assert manager.get_credentials(BrokerType.TRADIER, "tradier123") is None
    
    def test_token_expiry(self):
        """Test token expiry checking."""
        from datetime import timedelta
        
        # Expired token
        expired_creds = BrokerCredentials(
            broker=BrokerType.SCHWAB,
            account_id="expired",
            token_expiry=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        assert expired_creds.is_expired is True
        
        # Valid token
        valid_creds = BrokerCredentials(
            broker=BrokerType.SCHWAB,
            account_id="valid",
            token_expiry=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        assert valid_creds.is_expired is False


# =============================================================================
# Test Broker Factory
# =============================================================================

class TestBrokerFactory:
    """Tests for broker factory."""
    
    def test_create_alpaca(self, alpaca_credentials):
        """Test creating Alpaca broker."""
        broker = create_broker(
            broker_type=BrokerType.ALPACA,
            credentials=alpaca_credentials,
            sandbox=True,
        )
        
        assert broker is not None
        assert broker.broker_type == BrokerType.ALPACA
    
    def test_create_schwab(self):
        """Test creating Schwab broker."""
        broker = create_broker(
            broker_type=BrokerType.SCHWAB,
            credentials={"access_token": "test"},
        )
        
        assert broker is not None
        assert broker.broker_type == BrokerType.SCHWAB
    
    def test_create_mock(self):
        """Test creating mock broker for unsupported type."""
        broker = create_broker(
            broker_type=BrokerType.ETRADE,
            credentials={},
        )
        
        assert broker is not None


# =============================================================================
# Test Alpaca Broker
# =============================================================================

class TestAlpacaBroker:
    """Tests for Alpaca broker."""
    
    @pytest.mark.asyncio
    async def test_connect(self, alpaca_credentials):
        """Test connecting to Alpaca."""
        broker = create_broker(
            broker_type=BrokerType.ALPACA,
            credentials=alpaca_credentials,
            sandbox=True,
        )
        
        connected = await broker.connect()
        assert connected is True
        assert broker.is_connected() is True
    
    @pytest.mark.asyncio
    async def test_get_account(self, alpaca_credentials):
        """Test getting account info."""
        broker = create_broker(
            broker_type=BrokerType.ALPACA,
            credentials=alpaca_credentials,
            sandbox=True,
        )
        await broker.connect()
        
        account = await broker.get_account()
        assert account is not None
        assert account.broker == BrokerType.ALPACA
    
    @pytest.mark.asyncio
    async def test_get_balances(self, alpaca_credentials):
        """Test getting balances."""
        broker = create_broker(
            broker_type=BrokerType.ALPACA,
            credentials=alpaca_credentials,
            sandbox=True,
        )
        await broker.connect()
        
        balances = await broker.get_balances()
        assert balances is not None
        assert balances.buying_power > 0
    
    @pytest.mark.asyncio
    async def test_get_positions(self, alpaca_credentials):
        """Test getting positions."""
        broker = create_broker(
            broker_type=BrokerType.ALPACA,
            credentials=alpaca_credentials,
            sandbox=True,
        )
        await broker.connect()
        
        positions = await broker.get_positions()
        assert isinstance(positions, list)
        assert len(positions) >= 0
    
    @pytest.mark.asyncio
    async def test_place_order(self, alpaca_credentials, order_request):
        """Test placing an order."""
        broker = create_broker(
            broker_type=BrokerType.ALPACA,
            credentials=alpaca_credentials,
            sandbox=True,
        )
        await broker.connect()
        
        result = await broker.place_order(order_request)
        assert result.success is True
        assert result.order_id is not None
    
    @pytest.mark.asyncio
    async def test_get_quote(self, alpaca_credentials):
        """Test getting a quote."""
        broker = create_broker(
            broker_type=BrokerType.ALPACA,
            credentials=alpaca_credentials,
            sandbox=True,
        )
        await broker.connect()
        
        quote = await broker.get_quote("AAPL")
        assert quote is not None
        assert quote.symbol == "AAPL"
        assert quote.bid > 0


# =============================================================================
# Test Broker Manager
# =============================================================================

class TestBrokerManager:
    """Tests for BrokerManager."""
    
    @pytest.mark.asyncio
    async def test_add_broker(self, alpaca_credentials):
        """Test adding a broker."""
        manager = BrokerManager()
        
        connection_id = await manager.add_broker(
            BrokerType.ALPACA,
            credentials=alpaca_credentials,
            sandbox=True,
        )
        
        assert connection_id is not None
        connections = manager.get_connections()
        assert len(connections) == 1
    
    @pytest.mark.asyncio
    async def test_remove_broker(self, alpaca_credentials):
        """Test removing a broker."""
        manager = BrokerManager()
        
        connection_id = await manager.add_broker(
            BrokerType.ALPACA,
            credentials=alpaca_credentials,
            sandbox=True,
        )
        
        success = await manager.remove_broker(connection_id)
        assert success is True
        assert len(manager.get_connections()) == 0
    
    @pytest.mark.asyncio
    async def test_get_all_positions(self, alpaca_credentials):
        """Test getting all positions."""
        manager = BrokerManager()
        
        await manager.add_broker(
            BrokerType.ALPACA,
            credentials=alpaca_credentials,
            sandbox=True,
        )
        
        positions = await manager.get_all_positions()
        assert isinstance(positions, list)
    
    @pytest.mark.asyncio
    async def test_get_total_portfolio_value(self, alpaca_credentials):
        """Test getting total portfolio value."""
        manager = BrokerManager()
        
        await manager.add_broker(
            BrokerType.ALPACA,
            credentials=alpaca_credentials,
            sandbox=True,
        )
        
        total = await manager.get_total_portfolio_value()
        assert total > 0
    
    @pytest.mark.asyncio
    async def test_aggregated_positions(self, alpaca_credentials):
        """Test getting aggregated positions."""
        manager = BrokerManager()
        
        await manager.add_broker(
            BrokerType.ALPACA,
            credentials=alpaca_credentials,
            sandbox=True,
        )
        
        aggregated = await manager.get_aggregated_positions()
        assert isinstance(aggregated, dict)
    
    @pytest.mark.asyncio
    async def test_place_order(self, alpaca_credentials, order_request):
        """Test placing order through manager."""
        manager = BrokerManager()
        
        connection_id = await manager.add_broker(
            BrokerType.ALPACA,
            credentials=alpaca_credentials,
            sandbox=True,
        )
        
        result = await manager.place_order(order_request, connection_id)
        assert result.success is True


# =============================================================================
# Test Models
# =============================================================================

class TestModels:
    """Tests for data models."""
    
    def test_quote_properties(self):
        """Test Quote computed properties."""
        quote = Quote(
            symbol="AAPL",
            bid=184.50,
            ask=185.00,
            last=184.75,
        )
        
        assert quote.mid == 184.75
        assert quote.spread == 0.50
        assert quote.spread_pct == pytest.approx(0.27, rel=0.1)
    
    def test_order_request(self):
        """Test OrderRequest creation."""
        order = OrderRequest(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.LIMIT,
            limit_price=180.0,
            time_in_force=TimeInForce.GTC,
        )
        
        assert order.symbol == "AAPL"
        assert order.limit_price == 180.0
    
    def test_position(self):
        """Test Position model."""
        pos = Position(
            symbol="MSFT",
            quantity=50,
            average_cost=350.0,
            current_price=378.0,
        )
        
        pos.market_value = pos.quantity * pos.current_price
        pos.unrealized_pnl = pos.market_value - (pos.quantity * pos.average_cost)
        
        assert pos.market_value == 18900.0
        assert pos.unrealized_pnl == 1400.0
