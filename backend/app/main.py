import os
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.schemas import (Analysis, AnalysisRequest, Comparison, ComparisonRequest, Fund, IPOCatalogueResponse, IPOResearchResponse,
                         Rules, ScreenFilters, ScreenResponse, SearchResponse, SIPPortfolioAnalysis,
                         SIPPortfolioRequest, StatisticalSIPRequest, StatisticalSIPResponse)
from app.services.funds import FundService
from app.sources.base import SourceError


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.funds = FundService()
    yield
    await app.state.funds.close()


app = FastAPI(title="FundLens", version="0.1.0", lifespan=lifespan,
              description="Database-free Indian mutual-fund, statistical SIP and IPO research with traceable sources.")
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(","),
                   allow_methods=["GET", "POST"], allow_headers=["Content-Type"])


@app.exception_handler(SourceError)
async def source_error(request: Request, exc: SourceError):
    return JSONResponse(status_code=503, content={"detail": str(exc), "source_status": exc.status}, headers={"Retry-After": "30"})


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0", "storage": "memory-only"}


@app.get("/api/search", response_model=SearchResponse)
async def search(request: Request, q: str = Query(min_length=2, max_length=120),
                 plan: Literal["Direct", "Regular", ""] = "Direct", option: Literal["Growth", "IDCW", ""] = "Growth",
                 category: str = Query(default="", max_length=120), limit: int = Query(default=30, ge=1, le=100)):
    return await request.app.state.funds.search(q.strip(), plan, option, category, limit)


@app.get("/api/funds/{canonical_id}", response_model=Fund)
async def fund(canonical_id: str, request: Request):
    result = await request.app.state.funds.fund(canonical_id)
    if result is None:
        raise HTTPException(404, "Scheme not found in the current AMFI feed.")
    return result


@app.get("/api/funds/{canonical_id}/analysis", response_model=Analysis)
async def analysis(canonical_id: str, request: Request, rolling_years: Literal[1, 3, 5] = 3):
    return await run_analysis(request, canonical_id, None, rolling_years)


async def run_analysis(request, canonical_id, rules, rolling_years):
    result = await request.app.state.funds.analyse(canonical_id, rules, rolling_years)
    if result is None:
        raise HTTPException(404, "Scheme not found in the current AMFI feed.")
    return result


@app.post("/api/analyse", response_model=Analysis)
async def analyse(body: AnalysisRequest, request: Request):
    return await run_analysis(request, body.canonical_id, body.rules, body.rolling_years)


@app.post("/api/compare", response_model=Comparison)
async def compare(body: ComparisonRequest, request: Request):
    result = await request.app.state.funds.compare(body.canonical_ids, body.rules, body.rolling_years)
    if result is None:
        raise HTTPException(404, "One or more schemes were not found in the current AMFI feed.")
    return result


@app.post("/api/screen", response_model=ScreenResponse)
async def screen(body: ScreenFilters, request: Request):
    return await request.app.state.funds.screen(body)


@app.post("/api/portfolio/analyse", response_model=SIPPortfolioAnalysis)
async def portfolio_analyse(body: SIPPortfolioRequest, request: Request):
    result = await request.app.state.funds.analyse_portfolio(body)
    if result is None:
        raise HTTPException(404, "One or more schemes were not found in the current AMFI feed.")
    return result


@app.post("/api/sip/statistical-analysis", response_model=StatisticalSIPResponse)
async def statistical_sip(body: StatisticalSIPRequest, request: Request):
    result = await request.app.state.funds.statistical_sip(body)
    if result is None:
        raise HTTPException(404, "The scheme was not found in the current AMFI feed.")
    return result


@app.get("/api/ipos", response_model=IPOCatalogueResponse)
async def ipos(request: Request, q: str = Query(default="", max_length=120),
               board: Literal["Mainboard", "SME", ""] = "",
               status: Literal["open", "upcoming", "closed", ""] = ""):
    return await request.app.state.funds.ipo_catalogue(q, board, status)


@app.get("/api/ipos/{canonical_id}/research", response_model=IPOResearchResponse)
async def ipo_research(canonical_id: str, request: Request):
    result = await request.app.state.funds.ipo_research(canonical_id)
    if result is None:
        raise HTTPException(404, "IPO was not found in the current NSE issue catalogue.")
    return result


@app.get("/api/source-status")
async def sources(request: Request):
    funds = request.app.state.funds
    return [s.health() for s in funds.sources.values()] + [funds.market_source.health(), funds.history_source.health(),
                                                            funds.ipo_source.health()]


@app.get("/api/rules")
async def rules(request: Request):
    defaults = request.app.state.funds.defaults
    return {"defaults": Rules(**{k: v for k, v in defaults.items() if k != "category_rules"}),
            "category_rules": defaults.get("category_rules", {})}
