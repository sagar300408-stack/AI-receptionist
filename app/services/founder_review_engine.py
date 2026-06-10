import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.core.database import SessionLocal
from app.models.session import SessionORM
from app.models.profile import BusinessProfileORM
from app.models.solution import RecommendedSolutionORM
from app.models.review import ReviewSessionORM, FounderReviewORM, FounderFeedbackORM, ReviewAuditLogORM
from app.domain.review import (
    ReviewSessionStatus,
    ReviewStatus,
    CommercialReadiness,
    PriorityLevel,
    ReviewDecisionReason,
    PatternClassification,
    ReviewLifecyclePolicy,
)
from app.domain.events.base import (
    TviraDomainEvent,
    ReviewApprovedEvent,
    ReviewRejectedEvent,
    ReviewNeedsResearchEvent,
    ReviewArchivedEvent,
    ReviewCompletedEvent,
)
from app.services.event_bus import event_bus

logger = logging.getLogger("tvira.founder_review_engine")

class FounderReviewEngine:
    """Orchestrates review queues, state transitions, duplicate detection,
    audit logs, and human feedback management.
    """

    async def initialize_reviews_for_session(self, db: AsyncSession, session_id: UUID, recommended_solutions: List[Dict[str, Any]]) -> ReviewSessionORM:
        logger.info(f"Initializing founder review session and reviews for session {session_id}...")

        # 1. Fetch current business profile to get industry & team size for classification
        p_query = select(BusinessProfileORM).where(BusinessProfileORM.session_id == session_id)
        p_result = await db.execute(p_query)
        profile_orm = p_result.scalars().first()
        if not profile_orm:
            raise Exception(f"Business Profile for session {session_id} not found.")

        current_industry = profile_orm.industry
        current_team_size = profile_orm.team_size or 0

        # 2. Get or create ReviewSession
        sess_query = select(ReviewSessionORM).where(ReviewSessionORM.session_id == session_id)
        sess_result = await db.execute(sess_query)
        review_sess_orm = sess_result.scalars().first()

        now = datetime.now(timezone.utc)
        if not review_sess_orm:
            review_sess_orm = ReviewSessionORM(
                id=uuid4(),
                session_id=session_id,
                reviewer=None,
                status=ReviewSessionStatus.PENDING_REVIEW.value,
                started_at=None,
                completed_at=None,
                created_at=now
            )
            db.add(review_sess_orm)
            await db.flush()
            logger.info(f"Created new ReviewSession for session {session_id}.")

        # 3. Create individual reviews for recommendations
        for sol in recommended_solutions:
            sol_id_str = sol.get("id")
            if not sol_id_str:
                continue
            rec_id = UUID(sol_id_str)
            solution_type = sol.get("solution_type")

            # Check if FounderReview already exists
            rev_query = select(FounderReviewORM).where(FounderReviewORM.recommendation_id == rec_id)
            rev_result = await db.execute(rev_query)
            existing_rev = rev_result.scalars().first()

            if not existing_rev:
                # Classify opportunity pattern (deduplication)
                pattern = await self.classify_pattern(
                    db, session_id, solution_type, current_industry, current_team_size
                )

                # Fetch matching RecommendedSolution to get base priority score (from Phase 6 formula)
                base_priority_score = sol.get("priority_score", 50)

                review_orm = FounderReviewORM(
                    id=uuid4(),
                    review_session_id=review_sess_orm.id,
                    recommendation_id=rec_id,
                    review_status=ReviewStatus.PENDING_REVIEW.value,
                    review_decision=None,
                    decision_reason=None,
                    priority_level=self._map_score_to_level(base_priority_score),
                    priority_score=base_priority_score,
                    commercial_readiness=CommercialReadiness.NOT_READY.value,
                    pattern_classification=pattern,
                    created_at=now,
                    updated_at=now
                )
                db.add(review_orm)
                await db.flush()

                # Add Audit Log
                audit = ReviewAuditLogORM(
                    id=uuid4(),
                    review_id=review_orm.id,
                    action="INITIALIZED",
                    old_state=None,
                    new_state=ReviewStatus.PENDING_REVIEW.value,
                    timestamp=now
                )
                db.add(audit)
                logger.info(f"Initialized FounderReview for recommendation {rec_id} (Pattern: {pattern}).")

        await db.commit()
        return review_sess_orm

    async def start_review_session(self, db: AsyncSession, session_id: UUID, reviewer: str) -> ReviewSessionORM:
        logger.info(f"Starting review session for session {session_id} under reviewer '{reviewer}'...")
        sess_query = select(ReviewSessionORM).where(ReviewSessionORM.session_id == session_id)
        sess_result = await db.execute(sess_query)
        review_sess = sess_result.scalars().first()

        if not review_sess:
            raise Exception(f"Review Session for session {session_id} not found.")

        # Validate lifecycle transition
        ReviewLifecyclePolicy.validate_session_transition(
            ReviewSessionStatus(review_sess.status), ReviewSessionStatus.UNDER_REVIEW
        )

        now = datetime.now(timezone.utc)
        review_sess.status = ReviewSessionStatus.UNDER_REVIEW.value
        review_sess.reviewer = reviewer
        review_sess.started_at = now

        # Transition all pending reviews to UNDER_REVIEW
        rev_query = select(FounderReviewORM).where(FounderReviewORM.review_session_id == review_sess.id)
        rev_result = await db.execute(rev_query)
        reviews = list(rev_result.scalars().all())

        for r in reviews:
            if r.review_status == ReviewStatus.PENDING_REVIEW.value:
                r.review_status = ReviewStatus.UNDER_REVIEW.value
                r.updated_at = now
                audit = ReviewAuditLogORM(
                    id=uuid4(),
                    review_id=r.id,
                    action="START_REVIEW",
                    old_state=ReviewStatus.PENDING_REVIEW.value,
                    new_state=ReviewStatus.UNDER_REVIEW.value,
                    timestamp=now
                )
                db.add(audit)

        await db.commit()
        return review_sess

    async def approve_recommendation(
        self,
        db: AsyncSession,
        review_id: UUID,
        reviewer: Optional[str] = None,
        priority_score: Optional[int] = None,
        priority_level: Optional[str] = None,
        commercial_readiness: Optional[str] = None,
        decision_reason: Optional[str] = None,
        comment: Optional[str] = None,
        evidence_notes: Optional[str] = None
    ) -> FounderReviewORM:
        now = datetime.now(timezone.utc)
        review = await db.get(FounderReviewORM, review_id)
        if not review:
            raise Exception(f"FounderReview {review_id} not found.")

        # Validate state transition
        ReviewLifecyclePolicy.validate_review_transition(
            ReviewStatus(review.review_status), ReviewStatus.APPROVED
        )

        # Load session to get session_id & update reviewer
        review_session = await db.get(ReviewSessionORM, review.review_session_id)
        if reviewer and review_session:
            review_session.reviewer = reviewer

        old_status = review.review_status
        review.review_status = ReviewStatus.APPROVED.value
        review.review_decision = "APPROVED"
        review.decision_reason = decision_reason or ReviewDecisionReason.APPROVED.value
        review.updated_at = now

        if priority_score is not None:
            review.priority_score = priority_score
            # auto resolve level if not explicitly provided
            if not priority_level:
                review.priority_level = self._map_score_to_level(priority_score)
        if priority_level:
            review.priority_level = priority_level
        if commercial_readiness:
            review.commercial_readiness = commercial_readiness

        # Add Audit log
        audit = ReviewAuditLogORM(
            id=uuid4(),
            review_id=review.id,
            action="APPROVE",
            old_state=old_status,
            new_state=ReviewStatus.APPROVED.value,
            timestamp=now
        )
        db.add(audit)

        # Add Feedback record
        feedback = FounderFeedbackORM(
            id=uuid4(),
            review_id=review.id,
            comment=comment,
            decision_reason=review.decision_reason,
            evidence_notes=evidence_notes,
            created_at=now
        )
        db.add(feedback)

        await db.commit()
        await db.refresh(review)

        # Emit REVIEW_APPROVED event
        payload = {
            "priority_score": review.priority_score,
            "priority_level": review.priority_level,
            "commercial_readiness": review.commercial_readiness,
            "pattern_classification": review.pattern_classification,
            "decision_reason": review.decision_reason,
            "comment": comment
        }
        event = ReviewApprovedEvent(
            session_id=review_session.session_id if review_session else UUID(int=0),
            review_id=review.id,
            recommendation_id=review.recommendation_id,
            payload=payload,
            timestamp=now
        )
        await event_bus.publish(event)

        return review

    async def reject_recommendation(
        self,
        db: AsyncSession,
        review_id: UUID,
        decision_reason: str,
        comment: Optional[str] = None,
        evidence_notes: Optional[str] = None
    ) -> FounderReviewORM:
        now = datetime.now(timezone.utc)
        review = await db.get(FounderReviewORM, review_id)
        if not review:
            raise Exception(f"FounderReview {review_id} not found.")

        ReviewLifecyclePolicy.validate_review_transition(
            ReviewStatus(review.review_status), ReviewStatus.REJECTED
        )

        review_session = await db.get(ReviewSessionORM, review.review_session_id)

        old_status = review.review_status
        review.review_status = ReviewStatus.REJECTED.value
        review.review_decision = "REJECTED"
        review.decision_reason = decision_reason
        review.updated_at = now

        # Add Audit log
        audit = ReviewAuditLogORM(
            id=uuid4(),
            review_id=review.id,
            action="REJECT",
            old_state=old_status,
            new_state=ReviewStatus.REJECTED.value,
            timestamp=now
        )
        db.add(audit)

        # Add Feedback record
        feedback = FounderFeedbackORM(
            id=uuid4(),
            review_id=review.id,
            comment=comment,
            decision_reason=decision_reason,
            evidence_notes=evidence_notes,
            created_at=now
        )
        db.add(feedback)

        await db.commit()
        await db.refresh(review)

        event = ReviewRejectedEvent(
            session_id=review_session.session_id if review_session else UUID(int=0),
            review_id=review.id,
            recommendation_id=review.recommendation_id,
            payload={"decision_reason": decision_reason, "comment": comment},
            timestamp=now
        )
        await event_bus.publish(event)

        return review

    async def research_recommendation(self, db: AsyncSession, review_id: UUID, comment: Optional[str] = None) -> FounderReviewORM:
        now = datetime.now(timezone.utc)
        review = await db.get(FounderReviewORM, review_id)
        if not review:
            raise Exception(f"FounderReview {review_id} not found.")

        ReviewLifecyclePolicy.validate_review_transition(
            ReviewStatus(review.review_status), ReviewStatus.NEEDS_RESEARCH
        )

        review_session = await db.get(ReviewSessionORM, review.review_session_id)

        old_status = review.review_status
        review.review_status = ReviewStatus.NEEDS_RESEARCH.value
        review.review_decision = "NEEDS_RESEARCH"
        review.updated_at = now

        audit = ReviewAuditLogORM(
            id=uuid4(),
            review_id=review.id,
            action="RESEARCH",
            old_state=old_status,
            new_state=ReviewStatus.NEEDS_RESEARCH.value,
            timestamp=now
        )
        db.add(audit)

        feedback = FounderFeedbackORM(
            id=uuid4(),
            review_id=review.id,
            comment=comment,
            decision_reason=ReviewDecisionReason.INSUFFICIENT_EVIDENCE.value,
            evidence_notes=None,
            created_at=now
        )
        db.add(feedback)

        await db.commit()
        await db.refresh(review)

        event = ReviewNeedsResearchEvent(
            session_id=review_session.session_id if review_session else UUID(int=0),
            review_id=review.id,
            recommendation_id=review.recommendation_id,
            payload={"comment": comment},
            timestamp=now
        )
        await event_bus.publish(event)

        return review

    async def archive_recommendation(self, db: AsyncSession, review_id: UUID, comment: Optional[str] = None) -> FounderReviewORM:
        now = datetime.now(timezone.utc)
        review = await db.get(FounderReviewORM, review_id)
        if not review:
            raise Exception(f"FounderReview {review_id} not found.")

        ReviewLifecyclePolicy.validate_review_transition(
            ReviewStatus(review.review_status), ReviewStatus.ARCHIVED
        )

        review_session = await db.get(ReviewSessionORM, review.review_session_id)

        old_status = review.review_status
        review.review_status = ReviewStatus.ARCHIVED.value
        review.review_decision = "ARCHIVED"
        review.updated_at = now

        audit = ReviewAuditLogORM(
            id=uuid4(),
            review_id=review.id,
            action="ARCHIVE",
            old_state=old_status,
            new_state=ReviewStatus.ARCHIVED.value,
            timestamp=now
        )
        db.add(audit)

        feedback = FounderFeedbackORM(
            id=uuid4(),
            review_id=review.id,
            comment=comment,
            decision_reason=ReviewDecisionReason.OUT_OF_SCOPE.value,
            evidence_notes=None,
            created_at=now
        )
        db.add(feedback)

        await db.commit()
        await db.refresh(review)

        event = ReviewArchivedEvent(
            session_id=review_session.session_id if review_session else UUID(int=0),
            review_id=review.id,
            recommendation_id=review.recommendation_id,
            payload={"comment": comment},
            timestamp=now
        )
        await event_bus.publish(event)

        return review

    async def complete_review_session(self, db: AsyncSession, session_id: UUID) -> ReviewSessionORM:
        logger.info(f"Completing review session for session {session_id}...")
        sess_query = select(ReviewSessionORM).where(ReviewSessionORM.session_id == session_id)
        sess_result = await db.execute(sess_query)
        review_sess = sess_result.scalars().first()

        if not review_sess:
            raise Exception(f"Review Session for session {session_id} not found.")

        ReviewLifecyclePolicy.validate_session_transition(
            ReviewSessionStatus(review_sess.status), ReviewSessionStatus.COMPLETED
        )

        now = datetime.now(timezone.utc)
        review_sess.status = ReviewSessionStatus.COMPLETED.value
        review_sess.completed_at = now

        # Fetch reviews and count approved
        rev_query = select(FounderReviewORM).where(FounderReviewORM.review_session_id == review_sess.id)
        rev_result = await db.execute(rev_query)
        reviews = list(rev_result.scalars().all())
        approved_count = sum(1 for r in reviews if r.review_status == ReviewStatus.APPROVED.value)

        await db.commit()

        # Emit REVIEW_COMPLETED event
        event = ReviewCompletedEvent(
            session_id=session_id,
            review_session_id=review_sess.id,
            reviewer=review_sess.reviewer or "Unknown",
            approved_count=approved_count,
            timestamp=now
        )
        await event_bus.publish(event)

        return review_sess

    async def approve_all_reviews_for_session(self, db: AsyncSession, session_id: UUID, reviewer: str = "System Test") -> ReviewSessionORM:
        """Helper to bulk-approve all reviews in a session for test script execution."""
        logger.info(f"Running bulk approval helper for session {session_id}...")
        
        sess_query = select(ReviewSessionORM).where(ReviewSessionORM.session_id == session_id)
        sess_result = await db.execute(sess_query)
        review_sess = sess_result.scalars().first()
        if not review_sess:
            raise Exception(f"Review Session for session {session_id} not found.")

        if review_sess.status == ReviewSessionStatus.PENDING_REVIEW.value:
            await self.start_review_session(db, session_id, reviewer)

        rev_query = select(FounderReviewORM).where(FounderReviewORM.review_session_id == review_sess.id)
        rev_result = await db.execute(rev_query)
        reviews = list(rev_result.scalars().all())

        for r in reviews:
            if r.review_status in [ReviewStatus.PENDING_REVIEW.value, ReviewStatus.UNDER_REVIEW.value]:
                await self.approve_recommendation(
                    db,
                    review_id=r.id,
                    reviewer=reviewer,
                    priority_score=r.priority_score or 90,
                    priority_level=r.priority_level or "HIGH",
                    commercial_readiness=CommercialReadiness.READY_FOR_PROPOSAL.value,
                    decision_reason=ReviewDecisionReason.APPROVED.value,
                    comment="Auto-approved during E2E verification test.",
                    evidence_notes="Bulk approved by verification tool."
                )

        completed_sess = await self.complete_review_session(db, session_id)
        return completed_sess

    async def classify_pattern(self, db: AsyncSession, current_session_id: UUID, solution_type: str, current_industry: str, current_team_size: int) -> str:
        current_size = self._classify_business_size(current_team_size)

        hist_query = select(RecommendedSolutionORM, BusinessProfileORM).join(
            FounderReviewORM, RecommendedSolutionORM.id == FounderReviewORM.recommendation_id
        ).join(
            BusinessProfileORM, RecommendedSolutionORM.session_id == BusinessProfileORM.session_id
        ).where(
            RecommendedSolutionORM.solution_type == solution_type,
            FounderReviewORM.review_status == "APPROVED",
            RecommendedSolutionORM.session_id != current_session_id
        )

        result = await db.execute(hist_query)
        rows = list(result.all())

        if not rows:
            return PatternClassification.NET_NEW_OPPORTUNITY.value

        has_template_match = False
        for _, hist_profile in rows:
            hist_size = self._classify_business_size(hist_profile.team_size)
            hist_industry = hist_profile.industry or ""

            ind_match = (hist_industry.strip().lower() == (current_industry or "").strip().lower())
            size_match = (hist_size == current_size)

            if ind_match and size_match:
                has_template_match = True
                break

        if has_template_match:
            return PatternClassification.OPPORTUNITY_TEMPLATE.value
        else:
            return PatternClassification.OPPORTUNITY_VARIANT.value

    def _classify_business_size(self, team_size: Optional[int]) -> str:
        if team_size is None:
            return "SMALL"
        if team_size < 10:
            return "SMALL"
        elif 10 <= team_size <= 50:
            return "MEDIUM"
        else:
            return "LARGE"

    def _map_score_to_level(self, score: int) -> str:
        if score >= 80:
            return PriorityLevel.HIGH.value
        elif score >= 50:
            return PriorityLevel.MEDIUM.value
        else:
            return PriorityLevel.LOW.value

# Event listener mapping SOLUTIONS_RECOMMENDED to founder review session instantiation
async def on_solutions_recommended_listener(event: TviraDomainEvent):
    """Asynchronous subscriber caught on the Event Bus to decouple logic runs."""
    if event.event_type != "SOLUTIONS_RECOMMENDED":
        return

    logger.info(f"Founder Review Engine subscriber intercepting SOLUTIONS_RECOMMENDED for session: {event.session_id}")
    
    async with SessionLocal() as db:
        try:
            engine = FounderReviewEngine()
            recommended_sols = event.payload.get("recommended_solutions", [])
            await engine.initialize_reviews_for_session(db, event.session_id, recommended_sols)
        except Exception as e:
            logger.error(f"Async founder reviews initialization failed for session {event.session_id}: {e}")

def register_founder_review_listeners():
    """Binds event subscribers to the domain Event Bus."""
    event_bus.subscribe("SOLUTIONS_RECOMMENDED", on_solutions_recommended_listener)
