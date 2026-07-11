"""
Elasticsearch service for indexing and searching documents.
"""

import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from elasticsearch import AsyncElasticsearch
from elasticsearch.helpers import async_bulk

logger = logging.getLogger(__name__)


class ElasticsearchService:
    """Service for Elasticsearch operations."""

    def __init__(
        self,
        hosts: List[str] = None,
        index_name: str = "mpesa_transactions",
        use_ssl: bool = False,
        verify_certs: bool = False,
        username: str = None,
        password: str = None,
    ):
        self.hosts = hosts or ["http://localhost:9200"]
        self.index_name = index_name
        self.client = None
        self.use_ssl = use_ssl
        self.verify_certs = verify_certs
        self.username = username
        self.password = password
        self._connected = False

    async def connect(self):
        """Connect to Elasticsearch."""
        if self.username and self.password:
            self.client = AsyncElasticsearch(
                hosts=self.hosts,
                basic_auth=(self.username, self.password),
                verify_certs=self.verify_certs,
                use_ssl=self.use_ssl,
                request_timeout=60,
            )
        else:
            self.client = AsyncElasticsearch(
                hosts=self.hosts,
                verify_certs=self.verify_certs,
                use_ssl=self.use_ssl,
                request_timeout=60,
            )

        # Test connection
        try:
            info = await self.client.info()
            logger.info(f"✅ Connected to Elasticsearch {info['version']['number']}")
            self._connected = True
            await self._ensure_index()
        except Exception as e:
            logger.warning(f"⚠️ Failed to connect to Elasticsearch: {e}")
            self._connected = False

        return self

    async def close(self):
        """Close connection."""
        if self.client:
            await self.client.close()
            self._connected = False

    async def _ensure_index(self):
        """Create index with mapping if it doesn't exist."""
        # Check if index exists
        if await self.client.indices.exists(index=self.index_name):
            logger.debug(f"ℹ️ Index {self.index_name} already exists")
            return

        # Define mapping for M-PESA transactions
        mapping = {
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

    async def index_document(
        self,
        document_id: str,
        user_id: str,
        file_name: str,
        content: str,
        file_type: str = "pdf",
        file_size: int = 0,
        metadata: Dict[str, Any] = None,
        transactions: List[Dict[str, Any]] = None,
    ) -> str:
        """Index a document."""
        if not self._connected:
            logger.warning("Elasticsearch not connected, skipping index")
            return document_id

        try:
            document = {
                "document_id": document_id,
                "user_id": user_id,
                "file_name": file_name,
                "file_type": file_type,
                "file_size": file_size,
                "upload_date": datetime.now().isoformat(),
                "statement_type": (
                    metadata.get("statement_type", "mpesa") if metadata else "mpesa"
                ),
                "transaction_count": len(transactions) if transactions else 0,
                "total_income": sum(
                    t.get("amount", 0)
                    for t in (transactions or [])
                    if t.get("direction") == "in" or t.get("type") == "income"
                ),
                "total_expenses": sum(
                    t.get("amount", 0)
                    for t in (transactions or [])
                    if t.get("direction") == "out" or t.get("type") == "expense"
                ),
                "net_cash_flow": 0,  # Calculated in analysis
                "health_score": 0,  # Calculated in analysis
                "categories": list(
                    set(t.get("category", "Other") for t in (transactions or []))
                ),
                "merchants": list(
                    set(
                        t.get("merchant_name")
                        or t.get("till_number")
                        or t.get("paybill")
                        for t in (transactions or [])
                        if t.get("merchant_name")
                        or t.get("till_number")
                        or t.get("paybill")
                    )
                ),
                "transactions": (transactions or [])[:500],  # Limit for ES
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
        filters: Dict[str, Any] = None,
        page: int = 1,
        size: int = 20,
    ) -> Dict[str, Any]:
        """Search documents."""
        if not self._connected:
            return {"results": [], "total": 0, "error": "Elasticsearch not connected"}

        try:
            must = [{"term": {"user_id": user_id}}]

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

            search_body = {
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

            results = []
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

            return {
                "results": results,
                "total": response["hits"]["total"]["value"],
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
