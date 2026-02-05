"""Test script for Binance SDK migration verification.

Run this script to verify that the new binance-sdk-derivatives-trading-usds-futures
integration is working correctly.

Usage:
    python tests/test_binance_sdk_migration.py [OPTIONS]

Options:
    --testnet         Use Binance testnet instead of production
    --no-rest         Skip REST API tests
    --no-ws           Skip WebSocket tests
    --no-manager      Skip ThreadedManager tests
    --ws-timeout SEC  WebSocket test timeout in seconds (default: 30)

Environment Variables Required:
    - BINANCE_API_KEY: Your Binance API key
    - BINANCE_API_SECRET: Your Binance API secret

    For backwards compatibility, API_KEY and API_SECRET are also supported.

Examples:
    # Test on production
    python tests/test_binance_sdk_migration.py

    # Test on testnet
    python tests/test_binance_sdk_migration.py --testnet

    # Quick test (WebSocket only, 10 seconds)
    python tests/test_binance_sdk_migration.py --no-rest --no-manager --ws-timeout 10
"""

import os
import sys
import time
import logging
import argparse
from pathlib import Path

# Load .env file first to make environment variables available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.trading.binance_client import create_binance_client
from src.trading.binance_websocket import create_websocket_client
from src.config import ApiConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_rest_api(testnet: bool = False):
    """Test REST API functionality.

    Args:
        testnet: Use testnet instead of production
    """
    logger.info("=" * 60)
    logger.info(f"Testing REST API ({'testnet' if testnet else 'production'})")
    logger.info("=" * 60)

    try:
        # Load configuration
        config = ApiConfig.from_env()

        # Create client
        client = create_binance_client(
            api_key=config.api_key,
            api_secret=config.api_secret,
            testnet=testnet
        )
        logger.info("✓ REST client created successfully")

        # Test 1: Ping
        logger.info("\n[Test 1] Testing connectivity (ping)...")
        result = client.ping()
        logger.info("✓ Ping successful")

        # Test 2: Get symbol ticker
        logger.info("\n[Test 2] Getting symbol ticker...")
        ticker = client.get_symbol_ticker("BTCUSDT")
        logger.info(f"✓ BTCUSDT price: {ticker['price']}")

        # Test 3: Get klines
        logger.info("\n[Test 3] Getting kline data...")
        klines = client.futures_mark_price_klines(
            symbol="BTCUSDT",
            interval="1m",
            limit=10
        )
        logger.info(f"✓ Retrieved {len(klines)} klines")
        if klines:
            logger.info(f"  Latest kline: O={klines[-1][1]} H={klines[-1][2]} L={klines[-1][3]} C={klines[-1][4]}")

        # Test 4: Get position information
        logger.info("\n[Test 4] Getting position information...")
        positions = client.futures_position_information("BTCUSDT")
        logger.info(f"✓ Retrieved {len(positions)} positions")
        for pos in positions:
            if float(pos.get('positionAmount', 0)) != 0:
                logger.info(f"  {pos['symbol']}: {pos['positionAmount']} @ {pos['entryPrice']}")

        # Test 5: Change leverage (always run on testnet, skip on production unless user has no positions)
        if testnet:
            logger.info("\n[Test 5] Changing leverage...")
            result = client.futures_change_leverage("BTCUSDT", 10)
            logger.info(f"✓ Leverage changed: {result}")
        else:
            logger.info("\n[Test 5] Skipping leverage change on production")

        logger.info("\n" + "=" * 60)
        logger.info("REST API Tests: PASSED ✓")
        logger.info("=" * 60)
        return True

    except Exception as e:
        logger.error(f"\n✗ REST API Tests FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_websocket(testnet: bool = False, timeout: int = 30):
    """Test WebSocket functionality.

    Args:
        testnet: Use testnet instead of production
        timeout: Test timeout in seconds
    """
    logger.info("\n" + "=" * 60)
    logger.info(f"Testing WebSocket ({'testnet' if testnet else 'production'})")
    logger.info("=" * 60)

    try:
        # Load configuration
        config = ApiConfig.from_env()

        # Create WebSocket client
        ws_client = create_websocket_client(
            api_key=config.api_key,
            api_secret=config.api_secret,
            testnet=testnet
        )
        logger.info("✓ WebSocket client created successfully")

        # Test 1: Create kline stream
        logger.info("\n[Test 1] Creating kline stream...")
        stream_name = "test_kline_BTCUSDT_1m"
        stream_id = ws_client.create_stream(
            "kline",
            "BTCUSDT",
            interval="1m",
            stream_buffer_name=stream_name
        )
        logger.info(f"✓ Stream created with ID: {stream_id}")

        # Test 2: Read some data
        logger.info(f"\n[Test 2] Reading stream data (waiting {timeout} seconds)...")
        messages_received = 0
        start_time = time.time()

        while time.time() - start_time < timeout:
            data = ws_client.pop_stream_data_from_stream_buffer(stream_name)

            if data is not False:
                messages_received += 1
                if messages_received == 1:
                    logger.info("✓ First message received:")
                    logger.info(f"  Event type: {data.get('event_type')}")
                    if 'kline' in data:
                        kline = data['kline']
                        logger.info(f"  O: {kline.get('open_price')} "
                                  f"H: {kline.get('high_price')} "
                                  f"L: {kline.get('low_price')} "
                                  f"C: {kline.get('close_price')}")
                elif messages_received % 10 == 0:
                    logger.info(f"  Received {messages_received} messages so far...")

            time.sleep(0.1)

        logger.info(f"\n✓ Received {messages_received} messages in {timeout} seconds")

        if messages_received == 0:
            logger.warning("⚠ No messages received - this may indicate an issue with the WebSocket connection")

        # Test 3: Stop stream
        logger.info("\n[Test 3] Stopping stream...")
        ws_client.stop_stream(stream_id)
        logger.info("✓ Stream stopped")

        # Test 4: Stop manager
        logger.info("\n[Test 4] Stopping WebSocket manager...")
        ws_client.stop_manager_with_all_streams()
        logger.info("✓ WebSocket manager stopped")

        logger.info("\n" + "=" * 60)
        logger.info("WebSocket Tests: PASSED ✓")
        logger.info("=" * 60)
        return True

    except Exception as e:
        logger.error(f"\n✗ WebSocket Tests FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_threaded_manager(testnet: bool = False):
    """Test ThreadedManager integration.

    Args:
        testnet: Use testnet instead of production
    """
    logger.info("\n" + "=" * 60)
    logger.info(f"Testing ThreadedManager Integration ({'testnet' if testnet else 'production'})")
    logger.info("=" * 60)

    try:
        from src.threaded_manager import ThreadedManager

        # Override exchange for testnet
        if testnet:
            os.environ["BINANCE_EXCHANGE"] = "binance.com-futures-testnet"

        # Create manager
        manager = ThreadedManager(tf="1m", rate=1)
        logger.info("✓ ThreadedManager created successfully")

        # Check clients
        assert manager.client is not None, "REST client not initialized"
        logger.info("✓ REST client initialized")

        assert manager.bwsm is not None, "WebSocket client not initialized"
        logger.info("✓ WebSocket client initialized")

        # Test REST through manager
        logger.info("\n[Test] Testing REST through manager...")
        ticker = manager.client.get_symbol_ticker("BTCUSDT")
        logger.info(f"✓ BTCUSDT price: {ticker['price']}")

        # Cleanup
        logger.info("\n[Test] Stopping manager...")
        manager.stop(timeout=5)
        logger.info("✓ Manager stopped")

        logger.info("\n" + "=" * 60)
        logger.info("ThreadedManager Tests: PASSED ✓")
        logger.info("=" * 60)
        return True

    except Exception as e:
        logger.error(f"\n✗ ThreadedManager Tests FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    parser = argparse.ArgumentParser(
        description="Test Binance SDK migration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--testnet",
        action="store_true",
        help="Use Binance testnet instead of production"
    )
    parser.add_argument(
        "--no-rest",
        action="store_true",
        help="Skip REST API tests"
    )
    parser.add_argument(
        "--no-ws",
        action="store_true",
        help="Skip WebSocket tests"
    )
    parser.add_argument(
        "--no-manager",
        action="store_true",
        help="Skip ThreadedManager tests"
    )
    parser.add_argument(
        "--ws-timeout",
        type=int,
        default=30,
        help="WebSocket test timeout in seconds (default: 30)"
    )

    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("Binance SDK Migration Verification Tests")
    print(f"Environment: {'TESTNET' if args.testnet else 'PRODUCTION'}")
    print("=" * 60)

    # Check environment variables
    api_key = os.environ.get("BINANCE_API_KEY") or os.environ.get("API_KEY")
    api_secret = os.environ.get("BINANCE_API_SECRET") or os.environ.get("API_SECRET")

    if not api_key or not api_secret:
        logger.error("ERROR: BINANCE_API_KEY and BINANCE_API_SECRET environment variables must be set")
        logger.info("\nSet them with:")
        logger.info("  export BINANCE_API_KEY='your_api_key'")
        logger.info("  export BINANCE_API_SECRET='your_api_secret'")
        logger.info("\nOr create a .env file:")
        logger.info("  BINANCE_API_KEY=your_api_key")
        logger.info("  BINANCE_API_SECRET=your_api_secret")
        return 1

    results = {}

    # Run tests
    if not args.no_rest:
        results["REST API"] = test_rest_api(testnet=args.testnet)

    if not args.no_ws:
        results["WebSocket"] = test_websocket(testnet=args.testnet, timeout=args.ws_timeout)

    if not args.no_manager:
        results["ThreadedManager"] = test_threaded_manager(testnet=args.testnet)

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    for test_name, passed in results.items():
        status = "PASSED ✓" if passed else "FAILED ✗"
        print(f"  {test_name}: {status}")

    all_passed = all(results.values())
    print("=" * 60)

    if all_passed:
        print("\n🎉 All tests PASSED! Migration successful.")
        return 0
    else:
        print("\n❌ Some tests FAILED. Please review the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
