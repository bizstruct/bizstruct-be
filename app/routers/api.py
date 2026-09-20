from fastapi import APIRouter


from .users import router as users_router
from .auth import router as auth_router
# from .blocks import router as blocks_router
# from .generation import router as generation_router
# from .internal import router as internal_router
# from .models import router as models_router
# from .projects import router as projects_router
# from .system import router as system_router
# from .pubsub import router as pubsub_router


api_router = APIRouter(prefix="/api")

api_router.include_router(users_router)
api_router.include_router(auth_router)
# api_router.include_router(projects_router)
# api_router.include_router(blocks_router)
# api_router.include_router(generation_router)
# api_router.include_router(internal_router)
# api_router.include_router(models_router)
# api_router.include_router(system_router)
# api_router.include_router(pubsub_router)

