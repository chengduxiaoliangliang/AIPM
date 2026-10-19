from typing import List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import Department, User
from app.schemas.common import ResponseModel
from app.schemas.user import DepartmentCreate, DepartmentUpdate, DepartmentOut
from app.core.exceptions import NotFoundException, CustomException
from app.api.deps import get_current_user, PermissionChecker

router = APIRouter()

def build_dept_tree(depts: List[Department], parent_id: Optional[int] = None) -> List[DepartmentOut]:
    result = []
    for d in depts:
        if d.parent_id == parent_id:
            children = build_dept_tree(depts, d.id)
            dept_out = DepartmentOut(
                id=d.id,
                name=d.name,
                code=d.code,
                parent_id=d.parent_id,
                leader=d.leader,
                phone=d.phone,
                email=d.email,
                order_num=d.order_num,
                status=d.status,
                created_at=d.created_at,
                children=children
            )
            result.append(dept_out)
    return result

@router.get("", response_model=ResponseModel[List[DepartmentOut]])
def list_departments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    depts = db.query(Department).order_by(Department.order_num).all()
    tree = build_dept_tree(depts, None)
    return ResponseModel(code=200, message="success", data=tree)

@router.post("", response_model=ResponseModel[DepartmentOut])
def create_department(
    dept_in: DepartmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("system:dept:add"))
):
    if db.query(Department).filter(Department.code == dept_in.code).first():
        raise CustomException(message="部门编码已存在")

    new_dept = Department(
        name=dept_in.name,
        code=dept_in.code,
        parent_id=dept_in.parent_id,
        leader=dept_in.leader,
        phone=dept_in.phone,
        email=dept_in.email,
        order_num=dept_in.order_num,
        status=dept_in.status
    )
    db.add(new_dept)
    db.commit()
    db.refresh(new_dept)

    return ResponseModel(
        code=200,
        message="部门创建成功",
        data=DepartmentOut(
            id=new_dept.id,
            name=new_dept.name,
            code=new_dept.code,
            parent_id=new_dept.parent_id,
            leader=new_dept.leader,
            phone=new_dept.phone,
            email=new_dept.email,
            order_num=new_dept.order_num,
            status=new_dept.status,
            created_at=new_dept.created_at,
            children=[]
        )
    )

@router.put("/{dept_id}", response_model=ResponseModel[DepartmentOut])
def update_department(
    dept_id: int,
    dept_in: DepartmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("system:dept:edit"))
):
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        raise NotFoundException("部门不存在")

    if dept_in.name is not None:
        dept.name = dept_in.name
    if dept_in.code is not None:
        dept.code = dept_in.code
    if dept_in.parent_id is not None:
        if dept_in.parent_id == dept.id:
            raise CustomException(message="上级部门不能是自身")
        dept.parent_id = dept_in.parent_id
    if dept_in.leader is not None:
        dept.leader = dept_in.leader
    if dept_in.phone is not None:
        dept.phone = dept_in.phone
    if dept_in.email is not None:
        dept.email = dept_in.email
    if dept_in.order_num is not None:
        dept.order_num = dept_in.order_num
    if dept_in.status is not None:
        dept.status = dept_in.status

    db.commit()
    db.refresh(dept)

    return ResponseModel(
        code=200,
        message="部门更新成功",
        data=DepartmentOut(
            id=dept.id,
            name=dept.name,
            code=dept.code,
            parent_id=dept.parent_id,
            leader=dept.leader,
            phone=dept.phone,
            email=dept.email,
            order_num=dept.order_num,
            status=dept.status,
            created_at=dept.created_at,
            children=[]
        )
    )

@router.delete("/{dept_id}", response_model=ResponseModel[None])
def delete_department(
    dept_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("system:dept:delete"))
):
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        raise NotFoundException("部门不存在")
    if db.query(Department).filter(Department.parent_id == dept_id).first():
        raise CustomException(message="存在下级子部门，无法直接删除")
    if db.query(User).filter(User.department_id == dept_id).first():
        raise CustomException(message="部门下仍有用户，无法直接删除")

    db.delete(dept)
    db.commit()
    return ResponseModel(code=200, message="部门已成功删除")
