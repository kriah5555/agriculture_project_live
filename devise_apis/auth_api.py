"""
Mobile authentication and account request endpoints.

Routes (all mounted under /api/mobile/ via mobile_urls.py):
  POST  /auth/register/                     Register new user → access + refresh tokens
  POST  /auth/login/                        Login → access + refresh tokens
  POST  /auth/refresh/                      Get new access token
  POST  /auth/logout/                       Blacklist refresh token
  POST  /auth/forgot-password/              Forgot password → notifies admin (no auth)
  POST  /account/change-password-request/   Change password → notifies admin (auth required)
"""
from django.contrib.auth.models import User

from rest_framework import status
from rest_framework import serializers as drf_serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken

from drf_spectacular.utils import extend_schema, OpenApiResponse, inline_serializer

from .mobile_serializers import MobileTokenObtainSerializer


# ── Reusable inline schemas ───────────────────────────────────────────────────

_login_request = inline_serializer(
    name='LoginRequest',
    fields={
        'username': drf_serializers.CharField(),
        'password': drf_serializers.CharField(),
    },
)

_user_info_fields = {
    'id'                : drf_serializers.IntegerField(),
    'username'          : drf_serializers.CharField(),
    'email'             : drf_serializers.EmailField(),
    'first_name'        : drf_serializers.CharField(),
    'last_name'         : drf_serializers.CharField(),
    'full_name'         : drf_serializers.CharField(),
    'is_superuser'      : drf_serializers.BooleanField(),
    'is_staff'          : drf_serializers.BooleanField(),
    'is_active'         : drf_serializers.BooleanField(),
    'date_joined'       : drf_serializers.CharField(),
    'last_login'        : drf_serializers.CharField(allow_null=True),
    'user_type'         : drf_serializers.CharField(allow_null=True,
                            help_text='soil_partner | current_user | null (for superuser/staff)'),
    'state'             : drf_serializers.CharField(allow_null=True),
    'district'          : drf_serializers.CharField(allow_null=True),
    'city_village'      : drf_serializers.CharField(allow_null=True),
    'is_profile_active' : drf_serializers.BooleanField(allow_null=True),
}

_login_response = inline_serializer(
    name='LoginResponse',
    fields={
        'access' : drf_serializers.CharField(help_text='JWT access token (valid 2 days)'),
        'refresh': drf_serializers.CharField(help_text='JWT refresh token (valid 15 days)'),
        'user'   : inline_serializer(name='LoginUserInfo', fields=_user_info_fields),
    },
)

_refresh_request = inline_serializer(
    name='RefreshRequest',
    fields={
        'refresh': drf_serializers.CharField(help_text='Your current refresh token'),
    },
)

_refresh_response = inline_serializer(
    name='RefreshResponse',
    fields={
        'access': drf_serializers.CharField(help_text='New JWT access token'),
    },
)

_logout_request = inline_serializer(
    name='LogoutRequest',
    fields={
        'refresh': drf_serializers.CharField(help_text='The refresh token to blacklist'),
    },
)

_forgot_password_request = inline_serializer(
    name='ForgotPasswordRequest',
    fields={
        'username': drf_serializers.CharField(),
        'email'   : drf_serializers.EmailField(),
        'phone'   : drf_serializers.CharField(required=False, allow_blank=True),
        'message' : drf_serializers.CharField(required=False, allow_blank=True),
    },
)

_change_password_request = inline_serializer(
    name='ChangePasswordRequest',
    fields={
        'message': drf_serializers.CharField(
            required=False, allow_blank=True,
            help_text='Optional note to admin',
        ),
    },
)

_message_response = inline_serializer(
    name='MessageResponse',
    fields={'detail': drf_serializers.CharField()},
)


# ── Login ─────────────────────────────────────────────────────────────────────

class MobileLoginView(TokenObtainPairView):
    """
    POST username + password → access token (2 days) + refresh token (15 days).

    Token lifetimes are controlled by `MOBILE_TOKEN_SETTINGS` in settings.py.
    """
    serializer_class   = MobileTokenObtainSerializer
    permission_classes = [AllowAny]

    @extend_schema(
        tags=['Auth'],
        summary='Login — obtain JWT tokens',
        description=(
            'Authenticate with username and password. Returns an access token '
            '(valid 2 days) and a refresh token (valid 15 days). '
            'Pass the access token as `Authorization: Bearer <token>` on all '
            'subsequent requests.\n\n'
            'Token lifetimes are configurable in `settings.MOBILE_TOKEN_SETTINGS`.'
        ),
        request=_login_request,
        responses={
            200: _login_response,
            401: OpenApiResponse(description='Invalid credentials'),
        },
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


# ── Token refresh ─────────────────────────────────────────────────────────────

class MobileRefreshView(TokenRefreshView):
    """POST refresh token → new access token."""

    @extend_schema(
        tags=['Auth'],
        summary='Refresh access token',
        description=(
            'Exchange a valid refresh token for a new access token. '
            'The refresh token is rotated on each use (old one is blacklisted).'
        ),
        request=_refresh_request,
        responses={
            200: _refresh_response,
            401: OpenApiResponse(description='Refresh token invalid or expired'),
        },
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


# ── Logout ────────────────────────────────────────────────────────────────────

@extend_schema(
    tags=['Auth'],
    summary='Logout — blacklist refresh token',
    request=_logout_request,
    responses={
        204: OpenApiResponse(description='Logged out successfully'),
        400: _message_response,
    },
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mobile_logout(request):
    """Blacklist the provided refresh token, invalidating the session."""
    refresh_token = request.data.get('refresh')
    if not refresh_token:
        return Response({'detail': 'refresh token required.'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        token = RefreshToken(refresh_token)
        token.blacklist()
    except Exception:
        return Response({'detail': 'Invalid token.'}, status=status.HTTP_400_BAD_REQUEST)
    return Response(status=status.HTTP_204_NO_CONTENT)


# ── Forgot password (public) ──────────────────────────────────────────────────

@extend_schema(
    tags=['Auth'],
    summary='Forgot password — send request to admin',
    description=(
        'Public endpoint (no auth required). '
        'User submits username + email; a UserRequest record is created and '
        'appears in the admin Notifications panel as a pending item. '
        'The admin then resets the password manually and marks it resolved.'
    ),
    request=_forgot_password_request,
    responses={
        201: _message_response,
        400: _message_response,
    },
)
@api_view(['POST'])
@permission_classes([AllowAny])
def forgot_password_request(request):
    """Create a Forgot Password request visible to admin in Notifications."""
    from agriapp.models import UserRequest

    username = (request.data.get('username') or '').strip()
    email    = (request.data.get('email')    or '').strip()
    phone    = (request.data.get('phone')    or '').strip()
    message  = (request.data.get('message')  or '').strip()

    if not username or not email:
        return Response(
            {'detail': 'username and email are required.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = User.objects.filter(username=username, email=email).first()

    UserRequest.objects.create(
        user         = user,
        username     = username,
        email        = email,
        phone        = phone,
        request_type = UserRequest.FORGOT_PASSWORD,
        message      = message or f"User '{username}' has requested a password reset via mobile app.",
    )

    return Response(
        {'detail': 'Your request has been sent. An admin will reset your password shortly.'},
        status=status.HTTP_201_CREATED,
    )


# ── Change password request (authenticated) ───────────────────────────────────

@extend_schema(
    tags=['Account'],
    summary='Request a password change — notifies admin',
    description=(
        'Authenticated endpoint. Creates a Change Password request in the admin '
        'Notifications panel. The admin resets the password and marks it resolved. '
        'Duplicate pending requests are blocked with HTTP 409.'
    ),
    request=_change_password_request,
    responses={
        201: _message_response,
        409: _message_response,
    },
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password_request(request):
    """Notify admin that the authenticated user wants their password changed."""
    from agriapp.models import UserRequest

    user    = request.user
    message = (request.data.get('message') or '').strip()

    if UserRequest.objects.filter(
        user=user,
        request_type=UserRequest.CHANGE_PASSWORD,
        status=UserRequest.STATUS_PENDING,
    ).exists():
        return Response(
            {'detail': 'You already have a pending password change request. Please wait for admin action.'},
            status=status.HTTP_409_CONFLICT,
        )

    UserRequest.objects.create(
        user         = user,
        username     = user.username,
        email        = user.email,
        request_type = UserRequest.CHANGE_PASSWORD,
        message      = message or f"User '{user.username}' has requested a password change via mobile app.",
    )

    return Response(
        {'detail': 'Your request has been sent to the admin.'},
        status=status.HTTP_201_CREATED,
    )


# ── Soil Partner Interest / Enquiry (public) ──────────────────────────────────

_soil_partner_enquiry_request = inline_serializer(
    name='SoilPartnerEnquiryRequest',
    fields={
        'name'   : drf_serializers.CharField(help_text='Full name of the enquirer'),
        'email'  : drf_serializers.EmailField(help_text='Contact email'),
        'phone'  : drf_serializers.CharField(help_text='Contact phone number'),
        'state'  : drf_serializers.CharField(required=False, allow_blank=True, help_text='State'),
        'city'   : drf_serializers.CharField(required=False, allow_blank=True, help_text='City or district'),
        'message': drf_serializers.CharField(required=False, allow_blank=True, help_text='Optional message'),
    },
)

@extend_schema(
    tags=['Auth'],
    summary='Express interest in becoming a Soil Partner',
    description=(
        'Public endpoint (no auth required). '
        'Any external user can submit their contact details and express interest '
        'in joining as a Soil Partner. A UserRequest record is created and appears '
        'in the admin Notifications panel as a pending item. '
        'Duplicate submissions (same email + pending status) return HTTP 409.'
    ),
    request=_soil_partner_enquiry_request,
    responses={
        201: _message_response,
        400: _message_response,
        409: _message_response,
    },
)
@api_view(['POST'])
@permission_classes([AllowAny])
def soil_partner_enquiry(request):
    """Create a Soil Partner Interest request visible to admin in Notifications."""
    from agriapp.models import UserRequest

    name    = (request.data.get('name')    or '').strip()
    email   = (request.data.get('email')   or '').strip()
    phone   = (request.data.get('phone')   or '').strip()
    state   = (request.data.get('state')   or '').strip()
    city    = (request.data.get('city')    or '').strip()
    message = (request.data.get('message') or '').strip()

    if not name or not email or not phone:
        return Response(
            {'detail': 'name, email, and phone are required.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if UserRequest.objects.filter(
        email=email,
        request_type=UserRequest.SOIL_PARTNER_INTEREST,
        status=UserRequest.STATUS_PENDING,
    ).exists():
        return Response(
            {'detail': 'An enquiry from this email is already pending. Our team will contact you shortly.'},
            status=status.HTTP_409_CONFLICT,
        )

    UserRequest.objects.create(
        user         = None,
        username     = name,
        email        = email,
        phone        = phone,
        request_type = UserRequest.SOIL_PARTNER_INTEREST,
        message      = message or f"{name} is interested in becoming a Soil Partner. State: {state}, City: {city}",
    )

    return Response(
        {'detail': 'Thank you for your interest! Our team will review your enquiry and contact you shortly.'},
        status=status.HTTP_201_CREATED,
    )


# ── User registration ─────────────────────────────────────────────────────────

_register_request = inline_serializer(
    name='RegisterRequest',
    fields={
        'username'  : drf_serializers.CharField(help_text='Unique username'),
        'password'  : drf_serializers.CharField(help_text='Password (min 6 chars)'),
        'email'     : drf_serializers.EmailField(help_text='Email address'),
        'first_name': drf_serializers.CharField(required=False, allow_blank=True),
        'last_name' : drf_serializers.CharField(required=False, allow_blank=True),
        'phone'     : drf_serializers.CharField(required=False, allow_blank=True),
    },
)

_register_response = inline_serializer(
    name='RegisterResponse',
    fields={
        'access' : drf_serializers.CharField(help_text='JWT access token'),
        'refresh': drf_serializers.CharField(help_text='JWT refresh token'),
        'user'   : inline_serializer(name='RegisterUserInfo', fields={
            'id'       : drf_serializers.IntegerField(),
            'username' : drf_serializers.CharField(),
            'email'    : drf_serializers.EmailField(),
            'full_name': drf_serializers.CharField(),
        }),
    },
)


@extend_schema(
    tags=['Auth'],
    summary='Register new user',
    description=(
        'Create a new user account. The user is automatically added to the '
        '`deviseowner` group and JWT tokens are returned so the app can '
        'log the user in immediately after registration.\n\n'
        'Devices must still be assigned by an admin after registration.'
    ),
    request=_register_request,
    responses={
        201: _register_response,
        400: _message_response,
    },
)
@api_view(['POST'])
@permission_classes([AllowAny])
def mobile_register(request):
    """Register a new mobile user and return JWT tokens."""
    from django.contrib.auth.models import Group

    username   = (request.data.get('username')   or '').strip()
    password   = (request.data.get('password')   or '').strip()
    email      = (request.data.get('email')      or '').strip()
    first_name = (request.data.get('first_name') or '').strip()
    last_name  = (request.data.get('last_name')  or '').strip()

    if not username or not password or not email:
        return Response(
            {'detail': 'username, password, and email are required.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if len(password) < 6:
        return Response(
            {'detail': 'Password must be at least 6 characters.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if User.objects.filter(username=username).exists():
        return Response(
            {'detail': 'Username already taken.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if User.objects.filter(email=email).exists():
        return Response(
            {'detail': 'An account with this email already exists.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = User.objects.create_user(
        username   = username,
        email      = email,
        password   = password,
        first_name = first_name,
        last_name  = last_name,
    )

    group, _ = Group.objects.get_or_create(name='deviseowner')
    user.groups.add(group)

    refresh = RefreshToken.for_user(user)
    return Response(
        {
            'access' : str(refresh.access_token),
            'refresh': str(refresh),
            'user'   : {
                'id'       : user.id,
                'username' : user.username,
                'email'    : user.email,
                'full_name': user.get_full_name(),
            },
        },
        status=status.HTTP_201_CREATED,
    )


# ── My Payment History (authenticated soil partner) ───────────────────────────

_payment_list_response = inline_serializer(
    name='PaymentListResponse',
    fields={
        'count'          : drf_serializers.IntegerField(),
        'total_amount'   : drf_serializers.DecimalField(max_digits=12, decimal_places=2),
        'paid_amount'    : drf_serializers.DecimalField(max_digits=12, decimal_places=2),
        'pending_amount' : drf_serializers.DecimalField(max_digits=12, decimal_places=2),
        'paid_count'     : drf_serializers.IntegerField(),
        'pending_count'  : drf_serializers.IntegerField(),
        'payments'       : drf_serializers.ListField(child=drf_serializers.DictField()),
    },
)

@extend_schema(
    tags=['Account'],
    summary='My payment history',
    description=(
        'Returns all payment records for the authenticated soil partner with paid/pending split totals.\n\n'
        'Optional filters (query params):\n'
        '- `status`: `pending` or `paid`\n'
        '- `date_from` / `date_to`: filter by created date (YYYY-MM-DD)\n'
        '- `paid_from` / `paid_to`: filter by paid date (YYYY-MM-DD)\n\n'
        'Non-soil-partner accounts receive HTTP 403.'
    ),
    responses={
        200: _payment_list_response,
        403: _message_response,
    },
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_payment_history(request):
    """
    List payment records for the authenticated soil partner.

    Optional query params:
      status      pending | paid
      date_from   YYYY-MM-DD  (created_at >=)
      date_to     YYYY-MM-DD  (created_at <=)
      paid_from   YYYY-MM-DD  (paid_at >=)
      paid_to     YYYY-MM-DD  (paid_at <=)
    """
    from agriapp.models import PartnerPayment
    from django.db.models import Sum, Q

    profile = getattr(request.user, 'profile', None)
    if not profile or profile.user_type != 'soil_partner':
        return Response({'detail': 'Only soil partners have payment records.'}, status=status.HTTP_403_FORBIDDEN)

    qs = (
        PartnerPayment.objects
        .filter(user=request.user)
        .select_related('farmer')
        .prefetch_related('attachments')
        .order_by('-created_at')
    )

    # ── filters ──────────────────────────────────────────────────────────────
    status_filter = request.GET.get('status', '').strip()
    date_from     = request.GET.get('date_from', '').strip()
    date_to       = request.GET.get('date_to', '').strip()
    paid_from     = request.GET.get('paid_from', '').strip()
    paid_to       = request.GET.get('paid_to', '').strip()

    if status_filter in ('pending', 'paid'):
        qs = qs.filter(status=status_filter)
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)
    if paid_from:
        qs = qs.filter(paid_at__date__gte=paid_from)
    if paid_to:
        qs = qs.filter(paid_at__date__lte=paid_to)

    # ── totals (on filtered queryset) ────────────────────────────────────────
    totals = qs.aggregate(
        total_amount   = Sum('amount'),
        paid_amount    = Sum('amount', filter=Q(status='paid')),
        pending_amount = Sum('amount', filter=Q(status='pending')),
    )
    total_amount   = totals['total_amount']   or 0
    paid_amount    = totals['paid_amount']    or 0
    pending_amount = totals['pending_amount'] or 0

    paid_count    = qs.filter(status='paid').count()
    pending_count = qs.filter(status='pending').count()

    # ── serialise payments ───────────────────────────────────────────────────
    payments = []
    for p in qs:
        payments.append({
            'id'          : p.pk,
            'amount'      : str(p.amount),
            'status'      : p.status,
            'description' : p.description,
            'farmer_id'   : p.farmer_id,
            'farmer_name' : p.farmer.farmer_name if p.farmer else None,
            'attachments' : [request.build_absolute_uri(att.file.url) for att in p.attachments.all()],
            'created_at'  : p.created_at.isoformat(),
            'paid_at'     : p.paid_at.isoformat() if p.paid_at else None,
        })

    return Response({
        'count'         : len(payments),
        'total_amount'  : str(total_amount),
        'paid_amount'   : str(paid_amount),
        'pending_amount': str(pending_amount),
        'paid_count'    : paid_count,
        'pending_count' : pending_count,
        'payments'      : payments,
    })