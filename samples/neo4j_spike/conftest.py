"""
pytest configuration for Neo4j spike tests

Provides fixtures for Neo4j driver and session management
"""

import logging

import pytest
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def neo4j_driver():
    """
    Session-scoped Neo4j driver fixture

    Connects to Neo4j instance at bolt://localhost:7687
    Verifies connection before tests start
    """
    driver = None
    max_retries = 5
    retry_count = 0

    while retry_count < max_retries:
        try:
            driver = GraphDatabase.driver(
                "bolt://localhost:7687",
                auth=("neo4j", "certus-test-password"),
                encrypted=False,
            )

            # Verify connection
            with driver.session() as session:
                session.run("RETURN 1")

            logger.info("✅ Connected to Neo4j at bolt://localhost:7687")
            break

        except ServiceUnavailable:
            retry_count += 1
            if retry_count < max_retries:
                logger.warning(f"⏳ Neo4j not ready, retrying ({retry_count}/{max_retries})...")
                import time

                time.sleep(2)
            else:
                pytest.fail("❌ Could not connect to Neo4j. Ensure 'docker-compose up neo4j' is running")

    yield driver

    driver.close()
    logger.info("🔌 Disconnected from Neo4j")


@pytest.fixture
def neo4j_session(neo4j_driver):
    """
    Function-scoped Neo4j session fixture

    Creates fresh session for each test
    Clears graph before and after test (isolation)
    """
    session = neo4j_driver.session()

    # Clear graph before test
    try:
        session.run("MATCH (n) DETACH DELETE n")
        logger.debug("✓ Graph cleared before test")
    except Exception:
        logger.exception("Failed to clear graph before test")

    yield session

    # Cleanup after test
    try:
        session.run("MATCH (n) DETACH DELETE n")
        logger.debug("✓ Graph cleared after test")
    except Exception:
        logger.exception("Failed to cleanup graph after test")

    session.close()


@pytest.fixture
def neo4j_loader(neo4j_driver):
    """
    Fixture providing EvidenceGraphLoader instance
    """
    from samples.neo4j_spike.loader import EvidenceGraphLoader

    return EvidenceGraphLoader(neo4j_driver)


# pytest configuration
def pytest_configure(config):
    """Register custom markers"""
    config.addinivalue_line("markers", "neo4j: mark test as requiring Neo4j")
    config.addinivalue_line("markers", "performance: mark test as performance benchmark")


def pytest_collection_modifyitems(config, items):
    """Add neo4j marker to all tests in this directory"""
    for item in items:
        # Add neo4j marker if not already present
        if "neo4j" not in [m.name for m in item.iter_markers()]:
            item.add_marker(pytest.mark.neo4j)


# Pytest options
pytest_plugins = []
