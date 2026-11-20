from playwright.sync_api import expect
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import create_database_engine
from app.models import AdminItem

USERNAME = "qa-operator"
PASSWORD = "isolated-qa-fixture-password"


def sign_in(page, base):
    page.goto(base)
    page.get_by_label("사용자명").fill(USERNAME)
    page.get_by_label("비밀번호").fill(PASSWORD)
    page.get_by_role("button", name="로그인").click()
    expect(page.get_by_role("heading", name="데이터 관리")).to_be_visible()


def fill_item(page, name, description=""):
    page.get_by_label("항목 이름").fill(name)
    page.get_by_label("설명").fill(description)


def read_items(path):
    engine = create_database_engine(path)
    try:
        with Session(engine) as session:
            return [(item.id, item.name, item.description) for item in session.scalars(select(AdminItem).order_by(AdminItem.id))]
    finally:
        engine.dispose()


def record(request, detail):
    request.node.qa_detail = detail
    print(detail)
