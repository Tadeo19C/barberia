from flask import Flask, render_template, redirect, url_for, flash, request
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, DateTimeField, TextAreaField
from wtforms.validators import DataRequired, Email, EqualTo
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime
from wtforms import SelectField, DateField
import locale
import random

app = Flask(__name__)

locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
# Clave secreta para CSRF
app.secret_key = 'a1f4d9c7e5b2f8a6c3d4e5f9b1a7d2e6'

# Configuración de la base de datos
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///barberia.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class Usuario(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    nombre_usuario = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    contraseña = db.Column(db.String(150), nullable=False)

    carritos = db.relationship('Carrito', back_populates='usuario')
    pedidos = db.relationship('Pedido', back_populates='usuario', lazy=True)


class Producto(db.Model):
    __tablename__ = 'productos'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre = db.Column(db.String(150), nullable=False)
    descripcion = db.Column(db.Text)
    precio = db.Column(db.Float, nullable=False)
    disponible = db.Column(db.Boolean, default=True)

    # Relación con CarritoProducto usando primaryjoin para evitar errores
    carrito_productos = db.relationship(
        'CarritoProducto',
        back_populates='producto',
        primaryjoin="Producto.id == CarritoProducto.producto_id"
    )


class Cita(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    fecha_cita = db.Column(db.DateTime, nullable=False)
    servicio = db.Column(db.String(150), nullable=False)
    estado = db.Column(db.String(50), default="pendiente")


class Carrito(db.Model):
    __tablename__ = 'carrito'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    usuario = db.relationship('Usuario', back_populates='carritos')

    productos_en_carrito = db.relationship('CarritoProducto', back_populates='carrito')


class CarritoProducto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    carrito_id = db.Column(db.Integer, db.ForeignKey('carrito.id'), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)  # Cambia 'producto.id' a 'productos.id'
    cantidad = db.Column(db.Integer, default=1)

    producto = db.relationship('Producto', back_populates='carrito_productos')
    carrito = db.relationship('Carrito', back_populates='productos_en_carrito')

class Pedido(db.Model):
    __tablename__ = 'pedidos'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    total = db.Column(db.Float, nullable=False)
    fecha = db.Column(db.DateTime, default=db.func.now())
    direccion = db.Column(db.String(255), nullable=False)  # Agregar el campo 'direccion'

    # Relación con el modelo Usuario
    usuario = db.relationship('Usuario', back_populates='pedidos', lazy=True)

    # Relación con el modelo DetallePedido
    detalles = db.relationship('DetallePedido', back_populates='pedido')


class DetallePedido(db.Model):
    __tablename__ = 'detalle_pedido'
    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey('pedidos.id'), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    cantidad = db.Column(db.Integer, default=1)
    precio = db.Column(db.Float, nullable=False)

    # Relación con Pedido
    pedido = db.relationship('Pedido', back_populates='detalles')

    # Relación con Producto
    producto = db.relationship('Producto')

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# Formularios
class RegisterForm(FlaskForm):
    nombre_usuario = StringField('Nombre de usuario', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    contraseña = PasswordField('Contraseña', validators=[DataRequired(), EqualTo('confirmar_contraseña')])
    confirmar_contraseña = PasswordField('Confirmar Contraseña')
    submit = SubmitField('Registrarse')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    contraseña = PasswordField('Contraseña', validators=[DataRequired()])
    submit = SubmitField('Iniciar sesión')

class CitaForm(FlaskForm):
    servicio = SelectField('Servicio', choices=[
        ('corte', 'Corte de Cabello'),
        ('cejas', 'Cejas'),
        ('facial', 'Facial'),
        ('barba', 'Afeitado de Barba'),
        ('otros', 'Otros')
    ], validators=[DataRequired()])
    fecha_cita = DateField('Fecha de la Cita', validators=[DataRequired()], format='%Y-%m-%d')
    submit = SubmitField('Agendar Cita')
# Rutas
@app.route('/')
def home():
    # Consulta los productos (limitado a 6 para el ejemplo)
    productos_limited = Producto.query.limit(6).all()

    # Consulta todas las citas y extrae el campo `servicio` de cada una
    citas = Cita.query.all()
    servicios_disponibles = {cita.servicio for cita in citas}  # Usamos un conjunto para evitar duplicados

    # Pasamos productos y servicios a la plantilla de inicio
    return render_template('home.html', productos=productos_limited, servicios=servicios_disponibles)


@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.contraseña.data).decode('utf-8')
        nuevo_usuario = Usuario(nombre_usuario=form.nombre_usuario.data, email=form.email.data, contraseña=hashed_password)
        db.session.add(nuevo_usuario)
        db.session.commit()
        flash('Cuenta creada exitosamente', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        usuario = Usuario.query.filter_by(email=form.email.data).first()
        if usuario and bcrypt.check_password_hash(usuario.contraseña, form.contraseña.data):
            login_user(usuario)
            flash('Has iniciado sesión exitosamente', 'success')
            return redirect(url_for('home'))
        else:
            flash('Inicio de sesión incorrecto. Por favor, verifica tus credenciales', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Has cerrado sesión', 'info')
    return redirect(url_for('home'))

@app.route('/cita', methods=['GET', 'POST'])
@login_required
def cita():
    form = CitaForm()
    if form.validate_on_submit():
        nueva_cita = Cita(usuario_id=current_user.id, fecha_cita=form.fecha_cita.data, servicio=form.servicio.data)
        db.session.add(nueva_cita)
        db.session.commit()
        flash('Cita agendada exitosamente', 'success')
        return redirect(url_for('home'))
    return render_template('cita.html', form=form)

@app.route('/citas')
@login_required
def mostrar_citas():
    citas = Cita.query.filter_by(usuario_id=current_user.id).all()
    return render_template('citas.html', citas=citas)

@app.route('/servicios')
@login_required
def servicios():
    # Consulta todas las citas y extrae el campo `servicio` de cada una
    citas = Cita.query.all()
    servicios_disponibles = {cita.servicio for cita in citas}  # Utiliza un conjunto para evitar duplicados
    return render_template('servicios.html', servicios=servicios_disponibles)

@app.route('/contacto')
@login_required
def contacto():
    return render_template('contacto.html')

@app.route('/productos')
def productos():
    productos = Producto.query.all()
    return render_template('productos.html', productos=productos)

@app.route('/comprar_producto/<int:producto_id>', methods=['POST'])
def comprar_producto(producto_id):
    producto = Producto.query.get_or_404(producto_id)
    if producto.disponible:
        # Aquí podrías añadir la lógica para el proceso de compra
        flash(f'Has comprado {producto.nombre} por ${producto.precio}', 'success')
    else:
        flash('El producto no está disponible en este momento', 'danger')
    return redirect(url_for('ver_carrito'))


@app.route('/agregar_al_carrito/<int:producto_id>', methods=['POST'])
def agregar_al_carrito(producto_id):
    producto = Producto.query.get_or_404(producto_id)
    if not current_user.is_authenticated:
        flash("Por favor, inicia sesión para agregar productos al carrito.", "warning")
        return redirect(url_for('login'))

    # Buscar o crear un carrito para el usuario
    carrito = Carrito.query.filter_by(usuario_id=current_user.id).first()
    if not carrito:
        carrito = Carrito(usuario_id=current_user.id)
        db.session.add(carrito)
        db.session.commit()

    # Verificar si el producto ya está en el carrito
    carrito_producto = CarritoProducto.query.filter_by(carrito_id=carrito.id, producto_id=producto.id).first()

    if carrito_producto:
        # Si el producto ya está en el carrito, aumentar la cantidad
        carrito_producto.cantidad += 1
    else:
        # Si el producto no está en el carrito, agregarlo con cantidad 1
        carrito_producto = CarritoProducto(carrito_id=carrito.id, producto_id=producto.id, cantidad=1)
        db.session.add(carrito_producto)

    # Guardar los cambios en la base de datos
    db.session.commit()

    # Mensaje de éxito y redirección al carrito
    flash(f"{producto.nombre} ha sido añadido a tu carrito.", "success")

    # Consulta de depuración para verificar el contenido de CarritoProducto
    productos_en_carrito = CarritoProducto.query.filter_by(carrito_id=carrito.id).all()
    print("Productos en carrito después de agregar:", [(p.producto.nombre, p.cantidad) for p in productos_en_carrito])

    return redirect(url_for('ver_carrito'))


@app.route('/carrito')
def ver_carrito():
    if not current_user.is_authenticated:
        flash("Por favor, inicia sesión para ver tu carrito.", "warning")
        return redirect(url_for('login'))

    carrito = Carrito.query.filter_by(usuario_id=current_user.id).first()

    # Crear el carrito si no existe
    if not carrito:
        carrito = Carrito(usuario_id=current_user.id)
        db.session.add(carrito)
        db.session.commit()
        print("Carrito creado automáticamente para el usuario:", current_user.id)

    productos_en_carrito = CarritoProducto.query.filter_by(carrito_id=carrito.id).all()

    # Consulta de depuración para ver los productos en el carrito
    print("Productos en el carrito:", [(p.producto.nombre, p.cantidad) for p in productos_en_carrito])


    return render_template('ver_carrito.html', productos=productos_en_carrito)

def procesar_pago(usuario, total):
    print(f"Procesando el pago para el usuario {usuario.id} por un total de ${total:.2f}")

    # Mostrar el resultado aleatorio de la simulación
    exito = random.choice([True, False])
    print(f"Resultado de la simulación de pago: {'Éxito' if exito else 'Fracaso'}")

    return exito


@app.route('/comprar', methods=['POST'])
def comprar():
    if not current_user.is_authenticated:
        flash("Por favor, inicia sesión para realizar la compra.", "warning")
        return redirect(url_for('login'))

    carrito = Carrito.query.filter_by(usuario_id=current_user.id).first()
    if not carrito or not carrito.productos_en_carrito:
        flash("Tu carrito está vacío.", "warning")
        return redirect(url_for('ver_carrito'))

    # Calcular el total de la compra
    total_compra = sum(item.producto.precio * item.cantidad for item in carrito.productos_en_carrito)

    # Redirigir al usuario a la página de confirmación de compra
    return redirect(url_for('confirmar_compra', total_compra=total_compra))


@app.route('/confirmar_compra', methods=['GET', 'POST'])
def confirmar_compra():
    if not current_user.is_authenticated:
        flash("Por favor, inicia sesión para realizar la compra.", "warning")
        return redirect(url_for('login'))

    # Obtener el carrito del usuario
    carrito = Carrito.query.filter_by(usuario_id=current_user.id).first()

    # Verificar si el carrito está vacío
    if not carrito or not carrito.productos_en_carrito:
        flash("Tu carrito está vacío.", "warning")
        return redirect(url_for('ver_carrito'))

    # Obtener el total de la compra
    total_compra = sum(item.producto.precio * item.cantidad for item in carrito.productos_en_carrito)

    if request.method == 'POST':
        # Aquí procesas la compra y rediriges al flujo de pago
        direccion = request.form['direccion']
        metodo_pago = request.form['metodo_pago']

        # Puedes guardar esta información o pasarla a la función de pago
        pago_exitoso = procesar_pago(current_user, total_compra)

        if pago_exitoso:
            # Registrar la compra en la base de datos
            nueva_compra = Pedido(usuario_id=current_user.id, total=total_compra, direccion=direccion, metodo_pago=metodo_pago)
            db.session.add(nueva_compra)
            db.session.commit()

            # Vaciar el carrito después de la compra
            CarritoProducto.query.filter_by(carrito_id=carrito.id).delete()
            db.session.commit()

            flash("Compra realizada con éxito", 'success')
            return redirect(url_for('compra_exitosa'))

        else:
            flash("Hubo un problema con el pago. Inténtalo de nuevo.", "danger")
            return redirect(url_for('ver_carrito'))

    # Si es un GET, mostramos el resumen
    productos = carrito.productos_en_carrito
    return render_template('confirmar_compra.html', productos=productos, total_compra=total_compra)


@app.route('/compra_exitosa')
def compra_exitosa():
    return render_template('compra_exitosa.html')



if __name__ == '__main__':
    app.run(debug=True)
