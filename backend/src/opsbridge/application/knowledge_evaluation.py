"""Deterministic evaluation for lexical retrieval; no generative claims."""

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from opsbridge.application.knowledge import KnowledgeService
from opsbridge.domain.tickets import ActorRole


class RetrievalCase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=3, max_length=64)
    role: ActorRole
    query: str = Field(min_length=1, max_length=200)
    expected_chunks: list[str] = Field(max_length=10)
    expect_abstention: bool


class RetrievalDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset: str
    cases: list[RetrievalCase] = Field(min_length=1, max_length=100)


@dataclass(frozen=True)
class RetrievalMetrics:
    dataset: str
    cases: int
    answerable_cases: int
    expected_citations: int
    retrieved_citations: int
    matched_citations: int
    recall_at_3: float
    precision_at_3: float
    abstention_accuracy: float


def evaluate_retrieval(service: KnowledgeService, dataset: RetrievalDataset) -> RetrievalMetrics:
    expected_total = 0
    retrieved_total = 0
    matched_total = 0
    abstention_correct = 0
    for case in dataset.cases:
        result = service.search(query=case.query, role=case.role, limit=3)
        actual = {citation.chunk_id for citation in result.citations}
        expected = set(case.expected_chunks)
        expected_total += len(expected)
        retrieved_total += len(actual)
        matched_total += len(actual & expected)
        abstention_correct += int(result.abstained == case.expect_abstention)
    return RetrievalMetrics(
        dataset=dataset.dataset,
        cases=len(dataset.cases),
        answerable_cases=sum(bool(case.expected_chunks) for case in dataset.cases),
        expected_citations=expected_total,
        retrieved_citations=retrieved_total,
        matched_citations=matched_total,
        recall_at_3=matched_total / expected_total if expected_total else 1.0,
        precision_at_3=matched_total / retrieved_total if retrieved_total else 1.0,
        abstention_accuracy=abstention_correct / len(dataset.cases),
    )
