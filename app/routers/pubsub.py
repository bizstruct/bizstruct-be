


# @app.get("/api/negotiate", tags=["pubsub"])
# async def negotiate(project_id: uuid.UUID = Query(...)) -> dict[str, str]:
#     if not settings.azure_web_pubsub_connection_string:
#         raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="PubSub not configured")
#     return {"url": get_negotiate_url(str(project_id))}1