from fastapi import APIRouter

from app.api import analyses, applications, auth, cvs, health, journals, learning, questions, recommendations, rounds

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(applications.router)
api_router.include_router(rounds.router)
api_router.include_router(cvs.router)
api_router.include_router(analyses.router)
api_router.include_router(recommendations.router)
api_router.include_router(journals.router)
api_router.include_router(questions.router)
api_router.include_router(learning.router)
