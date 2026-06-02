from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.dependencies import require_advanced_user
from app.schemas.user import UserOut
from app.services.template_service import delete_template, list_templates, save_template_from_activity

router = APIRouter(tags=["templates"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/my/templates", response_class=HTMLResponse)
async def my_templates(
    request: Request,
    user: UserOut = Depends(require_advanced_user),
):
    items = list_templates(user.id)
    return templates.TemplateResponse(
        request,
        "activities/templates.html",
        {"user": user, "templates": items, "flash": request.query_params.get("msg")},
    )


@router.post("/activities/{activity_id}/save-template")
async def save_activity_template(
    activity_id: str,
    template_name: str = Form(...),
    user: UserOut = Depends(require_advanced_user),
):
    result = save_template_from_activity(activity_id, user.id, template_name)
    if not result:
        return RedirectResponse(
            f"/activities/{activity_id}/edit?msg=無法儲存範本",
            status_code=303,
        )
    return RedirectResponse(
        f"/activities/{activity_id}/edit?msg=範本「{result.name}」已儲存",
        status_code=303,
    )


@router.post("/my/templates/{template_id}/delete")
async def remove_template(
    template_id: str,
    user: UserOut = Depends(require_advanced_user),
):
    if delete_template(template_id, user.id):
        return RedirectResponse("/my/templates?msg=範本已刪除", status_code=303)
    return RedirectResponse("/my/templates?msg=無法刪除範本", status_code=303)
