from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import uvicorn
import logging
import uuid
# Ensure environment variables are loaded before initializing heavily
load_dotenv()

# Postpone importing langgraph things if necessary, but here we can import directly
# given load_dotenv() is called above.
from schemas import CampaignGenerateRequest
# The actual workflow export is standard, but if it relies on dot env it's fine.
from my_agent.agent import workflow

logger = logging.getLogger(__name__)

app = FastAPI(title="ReachAI Backend API")

# Setup CORS to allow Next.js local frontend to connect securely
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.post("/api/campaigns/generate")
async def generate_campaign(request: CampaignGenerateRequest):
    try:
        # Convert the Pydantic type into a dictionary for langgraph
        payload = request.model_dump()
        
        # Generate a unique thread ID per request to prevent cross-user state collisions
        # in the LangGraph memory saver
        
        config = {"configurable": {"thread_id": str(uuid.uuid4())}}
        
        logger.info(f"Initiating langgraph pipeline for brand: {request.brand.name} (Thread: {config['configurable']['thread_id']})")
        print(payload)
        
        # Execute the main workflow payload natively via langgraph
        final_state = await workflow.ainvoke(payload, config)
        print(final_state)
        return {"success": True, "data": final_state}
        
    except Exception as e:
        logger.error(f"Error during graph execution: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
