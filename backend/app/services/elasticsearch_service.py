"""
Elasticsearch service for indexing and searching documents.
"""

import json
import logging
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
import importlib
import os

logger = logging.getLogger(__name__)

# Check if aiohttp is available
try:
    import aiohttp

    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    logger.warning(
        "⚠️ aiohttp not installed. Elasticsearch async functionality will be limited."
    )

# Import Elasticsearch conditionally
try:
    from elasticsearch import AsyncElasticsearch
    from elasticsearch.helpers import async_bulk
    from elastic_transport import ApiResponse, NodeConfig

    ELASTICSEARCH_AVAILABLE = True
except ImportError:
    ELASTICSEARCH_AVAILABLE = False
    logger.warning(
        "⚠️ elasticsearch not installed. Elasticsearch functionality will be disabled."
    )


class ElasticsearchService:
    """Service for Elasticsearch operations."""

    def __init__(
        self,
        hosts: Optional[List[str]] = None,
        index_name: str = "mpesa_transactions",
        use_ssl: bool = False,
        verify_certs: bool = False,
        username: Optional[str] = None,
        password: Optional[str] = None,
        api_version: Optional[str] = None,  # Auto-detect if None
    ):
        self.hosts: List[str] = hosts or ["http://localhost:9200"]
        self.index_name: str = index_name
        self.client: Optional[Any] = None
        self.use_ssl: bool = use_ssl
        self.verify_certs: bool = verify_certs
        self.username: Optional[str] = username
        self.password: Optional[str] = password
        self.api_version: Optional[str] = api_version
        self._connected: bool = False

    async def connect(self) -> "ElasticsearchService":
        """Connect to Elasticsearch with automatic version detection."""
        if not ELASTICSEARCH_AVAILABLE:
            logger.warning("Elasticsearch not available, skipping connection")
            self._connected = False
            return self

        if not AIOHTTP_AVAILABLE:
            logger.warning(
                "aiohttp not installed. Please install it: pip install aiohttp"
            )
            self._connected = False
            return self

        # Try to detect Elasticsearch server version first
        server_version = await self._detect_server_version()

        if server_version:
            # Set API version based on server version
            if server_version.startswith("8."):
                self.api_version = "8"
            elif server_version.startswith("7."):
                self.api_version = "7"
            else:
                # Default to 8 if unknown
                self.api_version = "8"
            logger.info(
                f"✅ Detected Elasticsearch server version: {server_version}, using API version: {self.api_version}"
            )
        else:
            # If we can't detect, try version 8 first, then fallback to 7
            self.api_version = "8"

        try:
            # Determine scheme based on SSL
            scheme = "https" if self.use_ssl else "http"

            # Parse hosts to ensure they have the correct scheme
            parsed_hosts: List[str] = []
            for host in self.hosts:
                if not host.startswith(("http://", "https://")):
                    host = f"{scheme}://{host}"
                parsed_hosts.append(host)

            # Build connection parameters
            connection_params: Dict[str, Any] = {
                "hosts": parsed_hosts,
                "verify_certs": self.verify_certs,
                "request_timeout": 60,
            }

            # Add authentication if provided
            if self.username and self.password:
                connection_params["basic_auth"] = (self.username, self.password)

            # Try to connect with the detected API version
            if self.api_version:
                connection_params["headers"] = {
                    "Accept": f"application/vnd.elasticsearch+json; compatible-with={self.api_version}",
                    "Content-Type": "application/json",
                }

            # Create client
            self.client = AsyncElasticsearch(**connection_params)

            # Test connection
            try:
                if await self.client.ping():
                    logger.info("✅ Ping successful, Elasticsearch is reachable")
                    self._connected = True

                    # Get server info
                    try:
                        info = await self.client.info()
                        logger.info(
                            f"✅ Connected to Elasticsearch {info.get('version', {}).get('number', 'unknown')}"
                        )
                    except Exception as info_error:
                        logger.warning(f"⚠️ Could not get server info: {info_error}")

                    await self._ensure_index()
                    return self
                else:
                    logger.warning("⚠️ Ping failed, Elasticsearch may not be reachable")
                    self._connected = False
                    return self

            except Exception as e:
                # If version mismatch, try without version headers
                if "compatible-with" in str(e) or "media_type_header" in str(e):
                    logger.warning(
                        f"⚠️ Version compatibility issue, trying without version headers..."
                    )
                    # Remove version headers and retry
                    connection_params.pop("headers", None)
                    self.client = AsyncElasticsearch(**connection_params)

                    if await self.client.ping():
                        logger.info("✅ Ping successful without version headers")
                        self._connected = True
                        await self._ensure_index()
                        return self
                    else:
                        raise
                else:
                    raise

        except ImportError as e:
            logger.warning(f"⚠️ Failed to import Elasticsearch dependencies: {e}")
            self._connected = False
        except Exception as e:
            logger.warning(f"⚠️ Failed to connect to Elasticsearch: {e}")
            self._connected = False

        return self

    async def _detect_server_version(self) -> Optional[str]:
        """Try to detect the Elasticsearch server version."""
        try:
            import aiohttp

            # Try to connect without any version headers first
            async with aiohttp.ClientSession() as session:
                url = self.hosts[0]
                if not url.startswith(("http://", "https://")):
                    url = f"http://{url}"
                async with session.get(
                    f"{url}/", timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("version", {}).get("number")
        except Exception as e:
            logger.debug(f"Could not detect Elasticsearch version: {e}")

        return None

    async def close(self) -> None:
        """Close connection."""
        if self.client:
            try:
                await self.client.close()
            except Exception as e:
                logger.warning(f"⚠️ Error closing Elasticsearch connection: {e}")
            self._connected = False

    async def _ensure_index(self) -> None:
        """Create index with mapping if it doesn't exist."""
        if not self.client:
            logger.warning("Elasticsearch client not initialized")
            return

        try:
            # Check if index exists
            if await self.client.indices.exists(index=self.index_name):
                logger.debug(f"ℹ️ Index {self.index_name} already exists")
                return

            # Define mapping for M-PESA transactions
            mapping: Dict[str, Any] = {
                "settings": {
                    "number_of_shards": 2,
                    "number_of_replicas": 1,
                    "refresh_interval": "5s",
                    "analysis": {
                        "analyzer": {
                            "mpesa_analyzer": {
                                "type": "custom",
                                "tokenizer": "standard",
                                "filter": ["lowercase", "stop", "snowball"],
                            },
                            "ngram_analyzer": {
                                "type": "custom",
                                "tokenizer": "ngram_tokenizer",
                                "filter": ["lowercase"],
                            },
                        },
                        "tokenizer": {
                            "ngram_tokenizer": {
                                "type": "ngram",
                                "min_gram": 3,
                                "max_gram": 4,
                                "token_chars": ["letter", "digit"],
                            }
                        },
                    },
                },
                "mappings": {
                    "properties": {
                        "document_id": {"type": "keyword"},
                        "user_id": {"type": "keyword"},
                        "file_name": {
                            "type": "text",
                            "fields": {"keyword": {"type": "keyword"}},
                        },
                        "file_type": {"type": "keyword"},
                        "upload_date": {"type": "date"},
                        "statement_type": {"type": "keyword"},
                        "transaction_count": {"type": "integer"},
                        "total_income": {"type": "float"},
                        "total_expenses": {"type": "float"},
                        "net_cash_flow": {"type": "float"},
                        "health_score": {"type": "integer"},
                        "categories": {"type": "keyword"},
                        "merchants": {
                            "type": "text",
                            "fields": {"keyword": {"type": "keyword"}},
                        },
                        "insights": {"type": "text"},
                        "warnings": {"type": "text"},
                        "recommendations": {"type": "text"},
                        "processed_at": {"type": "date"},
                        "transactions": {
                            "type": "nested",
                            "properties": {
                                "receipt": {"type": "keyword"},
                                "date": {"type": "date"},
                                "time": {"type": "keyword"},
                                "description": {
                                    "type": "text",
                                    "analyzer": "mpesa_analyzer",
                                },
                                "amount": {"type": "float"},
                                "balance": {"type": "float"},
                                "direction": {"type": "keyword"},
                                "transaction_type": {"type": "keyword"},
                                "category": {"type": "keyword"},
                                "merchant_name": {
                                    "type": "text",
                                    "fields": {"keyword": {"type": "keyword"}},
                                },
                                "customer_name": {
                                    "type": "text",
                                    "fields": {"keyword": {"type": "keyword"}},
                                },
                                "phone": {"type": "keyword"},
                                "till": {"type": "keyword"},
                                "paybill": {"type": "keyword"},
                                "fuliza_used": {"type": "boolean"},
                                "fee": {"type": "float"},
                                "status": {"type": "keyword"},
                            },
                        },
                    }
                },
            }

            # Create index
            await self.client.indices.create(index=self.index_name, body=mapping)
            logger.info(f"✅ Created index: {self.index_name}")

        except Exception as e:
            logger.warning(f"⚠️ Failed to ensure index: {e}")

    async def index_document(
        self,
        document_id: str,
        user_id: str,
        file_name: str,
        content: str,
        file_type: str = "pdf",
        file_size: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
        transactions: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Index a document."""
        if not self._connected or not self.client:
            logger.warning("Elasticsearch not connected, skipping index")
            return document_id

        try:
            transactions_list = transactions or []

            document: Dict[str, Any] = {
                "document_id": document_id,
                "user_id": user_id,
                "file_name": file_name,
                "file_type": file_type,
                "file_size": file_size,
                "upload_date": datetime.now().isoformat(),
                "statement_type": (
                    metadata.get("statement_type", "mpesa") if metadata else "mpesa"
                ),
                "transaction_count": len(transactions_list),
                "total_income": sum(
                    t.get("amount", 0)
                    for t in transactions_list
                    if t.get("direction") == "in" or t.get("type") == "income"
                ),
                "total_expenses": sum(
                    t.get("amount", 0)
                    for t in transactions_list
                    if t.get("direction") == "out" or t.get("type") == "expense"
                ),
                "net_cash_flow": 0.0,
                "health_score": 0,
                "categories": list(
                    set(t.get("category", "Other") for t in transactions_list)
                ),
                "merchants": list(
                    set(
                        t.get("merchant_name")
                        or t.get("till_number")
                        or t.get("paybill")
                        for t in transactions_list
                        if t.get("merchant_name")
                        or t.get("till_number")
                        or t.get("paybill")
                    )
                ),
                "transactions": transactions_list[:500],
                "processed_at": datetime.now().isoformat(),
            }

            await self.client.index(
                index=self.index_name, id=document_id, body=document, refresh=True
            )
            logger.info(f"✅ Indexed document {document_id}")
            return document_id

        except Exception as e:
            logger.warning(f"⚠️ Failed to index document {document_id}: {e}")
            return document_id

    async def search(
        self,
        user_id: str,
        query: str = "",
        filters: Optional[Dict[str, Any]] = None,
        page: int = 1,
        size: int = 20,
    ) -> Dict[str, Any]:
        """Search documents."""
        if not self._connected or not self.client:
            return {"results": [], "total": 0, "error": "Elasticsearch not connected"}

        try:
            must: List[Dict[str, Any]] = [{"term": {"user_id": user_id}}]

            if query:
                must.append(
                    {
                        "multi_match": {
                            "query": query,
                            "fields": [
                                "file_name^2",
                                "transactions.description^1.5",
                                "transactions.merchant_name^1.5",
                                "categories",
                                "merchants",
                            ],
                            "fuzziness": "AUTO",
                        }
                    }
                )

            if filters:
                if filters.get("category"):
                    must.append({"term": {"categories": filters["category"]}})
                if filters.get("merchant"):
                    must.append({"term": {"merchants": filters["merchant"]}})
                if filters.get("start_date") and filters.get("end_date"):
                    must.append(
                        {
                            "range": {
                                "upload_date": {
                                    "gte": filters["start_date"],
                                    "lte": filters["end_date"],
                                }
                            }
                        }
                    )

            search_body: Dict[str, Any] = {
                "query": {"bool": {"must": must}} if must else {"match_all": {}},
                "from": (page - 1) * size,
                "size": size,
                "sort": [{"upload_date": {"order": "desc"}}],
                "aggs": {
                    "categories": {"terms": {"field": "categories", "size": 20}},
                    "merchants": {"terms": {"field": "merchants.keyword", "size": 20}},
                },
            }

            response = await self.client.search(index=self.index_name, body=search_body)

            results: List[Dict[str, Any]] = []
            for hit in response["hits"]["hits"]:
                source = hit["_source"]
                results.append(
                    {
                        "id": hit["_id"],
                        "file_name": source.get("file_name"),
                        "file_type": source.get("file_type"),
                        "transaction_count": source.get("transaction_count"),
                        "total_income": source.get("total_income", 0),
                        "total_expenses": source.get("total_expenses", 0),
                        "upload_date": source.get("upload_date"),
                        "score": hit.get("_score"),
                    }
                )

            total_hits = response["hits"]["total"]
            if isinstance(total_hits, dict):
                total_value = total_hits.get("value", 0)
            else:
                total_value = total_hits

            return {
                "results": results,
                "total": total_value,
                "page": page,
                "size": size,
                "aggregations": {
                    "categories": [
                        {"name": b["key"], "count": b["doc_count"]}
                        for b in response.get("aggregations", {})
                        .get("categories", {})
                        .get("buckets", [])
                    ],
                    "merchants": [
                        {"name": b["key"], "count": b["doc_count"]}
                        for b in response.get("aggregations", {})
                        .get("merchants", {})
                        .get("buckets", [])
                    ],
                },
            }

        except Exception as e:
            logger.warning(f"⚠️ Search failed: {e}")
            return {"results": [], "total": 0, "error": str(e)}

    async def bulk_index(
        self,
        documents: List[Dict[str, Any]],
        user_id: str,
    ) -> Dict[str, Any]:
        """Bulk index multiple documents."""
        if not self._connected or not self.client:
            return {"errors": True, "message": "Elasticsearch not connected"}

        try:
            if not ELASTICSEARCH_AVAILABLE:
                return {"errors": True, "message": "Elasticsearch not available"}

            actions: List[Dict[str, Any]] = []
            for doc in documents:
                actions.append(
                    {
                        "_index": self.index_name,
                        "_source": doc,
                    }
                )

            success, failed = await async_bulk(
                self.client,
                actions,
                refresh=True,
                stats_only=True,
            )

            logger.info(f"✅ Bulk indexed {success} documents, {failed} failed")
            return {"success": success, "failed": failed, "errors": failed > 0}

        except Exception as e:
            logger.error(f"❌ Bulk index failed: {e}")
            return {"errors": True, "message": str(e)}

    async def delete_document(self, document_id: str) -> bool:
        """Delete a document by ID."""
        if not self._connected or not self.client:
            return False

        try:
            await self.client.delete(
                index=self.index_name, id=document_id, refresh=True
            )
            logger.info(f"✅ Deleted document {document_id}")
            return True
        except Exception as e:
            logger.warning(f"⚠️ Failed to delete document {document_id}: {e}")
            return False

    async def delete_by_user(self, user_id: str) -> Dict[str, Any]:
        """Delete all documents for a user."""
        if not self._connected or not self.client:
            return {"deleted": 0, "error": "Elasticsearch not connected"}

        try:
            response = await self.client.delete_by_query(
                index=self.index_name,
                body={"query": {"term": {"user_id": user_id}}},
                refresh=True,
            )
            deleted = response.get("deleted", 0)
            logger.info(f"✅ Deleted {deleted} documents for user {user_id}")
            return {"deleted": deleted}
        except Exception as e:
            logger.error(f"❌ Failed to delete documents for user {user_id}: {e}")
            return {"deleted": 0, "error": str(e)}

    async def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get a document by ID."""
        if not self._connected or not self.client:
            return None

        try:
            response = await self.client.get(index=self.index_name, id=document_id)
            return response["_source"]
        except Exception as e:
            logger.warning(f"⚠️ Failed to get document {document_id}: {e}")
            return None

    def is_connected(self) -> bool:
        """Check if connected to Elasticsearch."""
        return self._connected and self.client is not None

    async def ping(self) -> bool:
        """Ping Elasticsearch."""
        if not self.client:
            return False
        try:
            return await self.client.ping()
        except Exception:
            return False

    async def refresh_index(self) -> bool:
        """Refresh the index."""
        if not self._connected or not self.client:
            return False
        try:
            await self.client.indices.refresh(index=self.index_name)
            return True
        except Exception as e:
            logger.warning(f"⚠️ Failed to refresh index: {e}")
            return False
