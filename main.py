import flask_login
from flask import Flask, render_template, request, url_for, redirect, session, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Integer, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from flask_login import LoginManager, UserMixin, login_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
from typing import List
import random



login_manager = LoginManager()


def guess_or_not(user):
    if "@" not in user.email:
        return True
    else:
        return False


def convert(string):
    li = list(string.split(", "))
    return li


class Base(DeclarativeBase):
  pass


db = SQLAlchemy(model_class=Base)
app = Flask(__name__)
app.jinja_env.globals.update(convert=convert)
login_manager.init_app(app)
app.secret_key = os.environ['SECRET_KEY']


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///project.db"
db.init_app(app)


class Task(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    task: Mapped[str] = mapped_column(unique=False, nullable=False)
    small_task: Mapped[str] = mapped_column(nullable=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_table.id"))
    user: Mapped["User"] = relationship(back_populates="tasks")
    page_id: Mapped[int] = mapped_column(ForeignKey("page_table.id"))
    page: Mapped["Pages"] = relationship(back_populates="tasks")


class DoneTask(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    done_task: Mapped[str] = mapped_column(unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_table.id"))
    user: Mapped["User"] = relationship(back_populates="done_tasks")
    page_id: Mapped[int] = mapped_column(ForeignKey("page_table.id"))
    page: Mapped["Pages"] = relationship(back_populates="done_tasks")


class User(UserMixin, db.Model):
    __tablename__ = "user_table"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(100), unique=True)
    password: Mapped[str] = mapped_column(String(100))
    tasks: Mapped[List["Task"]] = relationship(back_populates="user")
    done_tasks: Mapped[List["DoneTask"]] = relationship(back_populates="user")
    page: Mapped[List["Pages"]] = relationship(back_populates="user")


class Pages(db.Model):
    __tablename__ = "page_table"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), default="#page1")
    user_id: Mapped[int] = mapped_column(ForeignKey("user_table.id"))
    user: Mapped["User"] = relationship(back_populates="page")
    tasks: Mapped[List["Task"]] = relationship(back_populates="page")
    done_tasks: Mapped[List["DoneTask"]] = relationship(back_populates="page")


with app.app_context():
    db.create_all()


@app.route("/", methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        task = Task(task=request.form.get('task'),
                    small_task="",
                    user=flask_login.current_user)
        db.session.add(task)
        db.session.commit()
    if not flask_login.current_user.is_authenticated:
        user = User(
            email="guest" + str(random.randint(1,30000)),
            password=generate_password_hash(password=str(random.randint(1,30000)), salt_length=16)
        )
        db.session.add(user)
        db.session.commit()
        login_user(user)

    user = flask_login.current_user
    tasks = db.session.execute(db.select(Task).filter_by(user=user)).scalars()
    done_tasks = db.session.execute(db.select(DoneTask).filter_by(user=user)).scalars().all()
    pages = db.session.execute(db.select(Pages).filter_by(user=user)).scalars().all()
    if not pages:
        page = Pages(user=user)
        db.session.add(page)
        db.session.commit()


    return render_template("index.html", tasks=tasks, done_tasks=done_tasks, user=user,
                           is_guest=guess_or_not(user), pages=pages)


@app.route("/add_small_task/<task_picked>", methods=['GET', 'POST'])
def add(task_picked):
    if request.method == 'POST':
        user = flask_login.current_user
        task = db.session.execute(db.select(Task).filter_by(user=user, task=task_picked)).scalar()
        task.small_task = task.small_task + ", " + request.form.get("task")
        db.session.commit()
        return redirect(url_for('home'))
    user = flask_login.current_user
    tasks = db.session.execute(db.select(Task).filter_by(user=user)).scalars()
    done_tasks = db.session.execute(db.select(DoneTask).filter_by(user=user)).scalars().all()

    return render_template("add.html", tasks=tasks, task_picked=task_picked, done_tasks=done_tasks, user=user,
                           is_guess=guess_or_not(user))


@app.route("/complete/<task_picked>", methods=['GET', 'POST'])
def complete(task_picked):
    user = flask_login.current_user
    task = db.session.execute(db.select(Task).filter_by(user=user, task=task_picked)).scalar()
    donetask = DoneTask(
        done_task=task.task,
        user=user
    )
    db.session.delete(task)
    db.session.add(donetask)
    db.session.commit()
    return redirect(url_for("home"))


@app.route("/clear")
def clear():
    user = flask_login.current_user
    done_tasks = db.session.execute(db.select(DoneTask).filter_by(user=user)).scalars().all()
    for done_task in done_tasks:
        db.session.delete(done_task)
        db.session.commit()
    return redirect(url_for('home', is_guess=guess_or_not(user)))


@app.route("/delete/<task_picked>", methods=['GET', 'POST'])
def delete_task(task_picked):
    user = flask_login.current_user
    task = db.session.execute(db.select(Task).filter_by(user=user, task=task_picked)).scalar()
    db.session.delete(task)
    db.session.commit()
    return redirect(url_for('home', is_guess=guess_or_not(user)))


@app.route("/delete_small_task/<task_picked>/<small_picked>", methods=['GET', 'POST'])
def delete_small_task(task_picked, small_picked):
    task = db.one_or_404(db.select(Task).filter_by(task=task_picked))
    string_of_picked_small_task = task.small_task
    string_of_picked_small_task = string_of_picked_small_task.replace(small_picked, "")
    task.small_task = string_of_picked_small_task
    db.session.commit()
    return redirect(url_for('clear'))


@app.route("/login", methods=['GET', 'POST'])
def login():
    user_logged = flask_login.current_user
    if "@" not in user_logged.email:
        is_guest = True
    if request.method == "POST":
        input_email = request.form.get("email")
        input_password = request.form.get("password")
        result = db.session.execute(db.select(User).where(User.email == input_email))
        user = result.scalar()
        if user:
            if check_password_hash(user.password, input_password):
                login_user(user)
                return redirect(url_for('home'))
            else:
                flash("Wrong Password.")
        else:
            flash("This email hadn't been registered.")

    return render_template("login.html", user=flask_login.current_user, is_guest=is_guest)


@app.route("/create", methods=['GET', 'POST'])
def create():
    user_logged = flask_login.current_user
    is_guest = guess_or_not(user_logged)
    if request.method == "POST":
        inputted_email = request.form.get("email")
        inputted_password = request.form.get("password")
        result = db.session.execute(db.select(User).where(User.email == inputted_email))
        user = result.scalar()
        if user:
            flash("The email had been registered before.")
            return redirect(url_for('create'))
        else:
            user = User(
                email=inputted_email,
                password=generate_password_hash(password=inputted_password, salt_length=16)
            )
            db.session.add(user)
            db.session.commit()
            if is_guest:
                tasks = db.session.execute(db.select(Task).filter_by(user=user_logged)).scalars()
                done_tasks = db.session.execute(db.select(DoneTask).filter_by(user=user_logged)).scalars().all()
                for task in tasks:
                    task.user = user
                    db.session.add(task)
                    db.session.commit()
                for done_task in done_tasks:
                    done_task.user = user
                    db.session.add(done_task)
                    db.session.commit()
            login_user(user)
        return redirect(url_for('home'))
    return render_template("create.html", user=flask_login.current_user, is_guest=is_guest)

@app.route("/logout", methods=['GET', 'POST'])
def logout():
    flask_login.logout_user()
    return redirect(url_for("home"))



@app.route("/create_page", methods=['GET', 'POST'])
def create_page():
    if request.method == "POST":
        user = flask_login.current_user
        name = request.form.get("page_name")
        page = Pages(name=name,
                     user=user)
        result = db.session.execute(db.select(Pages).filter_by(user=user, name=name)).scalar()
        if not result:
            db.session.add(page)
            db.session.commit()
        else:
            flash("Page name already existed.")
    return redirect(url_for("home"))

app.run(debug=True)
