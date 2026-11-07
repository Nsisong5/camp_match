INFO:     127.0.0.1:34358 - "POST /api/v1/payments HTTP/1.1" 500 Internal Server Error
ERROR:    Exception in ASGI application
Traceback (most recent call last):
  File "/root/pt_workspace/lib/python3.14/site-packages/uvicorn/protocols/http/httptools_impl.py", line 422, in run_asgi
    result = await app(  # type: ignore[func-returns-value]
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        self.scope, self.receive, self.send
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/root/pt_workspace/lib/python3.14/site-packages/uvicorn/middleware/proxy_headers.py", line 63, in __call__
    return await self.app(scope, receive, send)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/root/pt_workspace/lib/python3.14/site-packages/fastapi/applications.py", line 1163, in __call__
    await super().__call__(scope, receive, send)
  File "/root/pt_workspace/lib/python3.14/site-packages/starlette/applications.py", line 96, in __call__
    await self.middleware_stack(scope, receive, send)
  File "/root/pt_workspace/lib/python3.14/site-packages/starlette/middleware/errors.py", line 186, in __call__
    raise exc
  File "/root/pt_workspace/lib/python3.14/site-packages/starlette/middleware/errors.py", line 164, in __call__
    await self.app(scope, receive, _send)
  File "/root/pt_workspace/lib/python3.14/site-packages/starlette/middleware/base.py", line 193, in __call__
    response = await self.dispatch_func(request, call_next)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/sdcard/cm_wkdir/camp_match/src/camp_match/platform/logging/middleware.py", line 18, in dispatch
    response = await call_next(request)
               ^^^^^^^^^^^^^^^^^^^^^^^^
  File "/root/pt_workspace/lib/python3.14/site-packages/starlette/middleware/base.py", line 168, in call_next
    raise app_exc from app_exc.__cause__ or app_exc.__context__
  File "/root/pt_workspace/lib/python3.14/site-packages/starlette/middleware/base.py", line 144, in coro
    await self.app(scope, receive_or_disconnect, send_no_error)
  File "/root/pt_workspace/lib/python3.14/site-packages/starlette/middleware/exceptions.py", line 63, in __call__
    await wrap_app_handling_exceptions(self.app, conn)(scope, receive, send)
  File "/root/pt_workspace/lib/python3.14/site-packages/starlette/_exception_handler.py", line 53, in wrapped_app
    raise exc
  File "/root/pt_workspace/lib/python3.14/site-packages/starlette/_exception_handler.py", line 42, in wrapped_app
    await app(scope, receive, sender)
  File "/root/pt_workspace/lib/python3.14/site-packages/fastapi/middleware/asyncexitstack.py", line 18, in __call__
    await self.app(scope, receive, send)
  File "/root/pt_workspace/lib/python3.14/site-packages/starlette/routing.py", line 670, in __call__
    await self.middleware_stack(scope, receive, send)
  File "/root/pt_workspace/lib/python3.14/site-packages/fastapi/routing.py", line 2734, in app
    await route.handle(scope, receive, send)
  File "/root/pt_workspace/lib/python3.14/site-packages/fastapi/routing.py", line 1780, in handle
    await self.original_router.handle(scope, receive, send)
  File "/root/pt_workspace/lib/python3.14/site-packages/fastapi/routing.py", line 2789, in handle
    await included_router._handle_selected(scope, receive, send)
  File "/root/pt_workspace/lib/python3.14/site-packages/fastapi/routing.py", line 1800, in _handle_selected
    await original_route.handle(scope, receive, send)
  File "/root/pt_workspace/lib/python3.14/site-packages/fastapi/routing.py", line 1279, in handle
    await app(scope, receive, send)
  File "/root/pt_workspace/lib/python3.14/site-packages/fastapi/routing.py", line 158, in app
    await wrap_app_handling_exceptions(app, request)(scope, receive, send)
  File "/root/pt_workspace/lib/python3.14/site-packages/starlette/_exception_handler.py", line 53, in wrapped_app
    raise exc
  File "/root/pt_workspace/lib/python3.14/site-packages/starlette/_exception_handler.py", line 42, in wrapped_app
    await app(scope, receive, sender)
  File "/root/pt_workspace/lib/python3.14/site-packages/fastapi/routing.py", line 144, in app
    response = await f(request)
               ^^^^^^^^^^^^^^^^
  File "/root/pt_workspace/lib/python3.14/site-packages/fastapi/routing.py", line 706, in app
    raw_response = await run_endpoint_function(
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    ...<3 lines>...
    )
    ^
  File "/root/pt_workspace/lib/python3.14/site-packages/fastapi/routing.py", line 352, in run_endpoint_function
    return await dependant.call(**values)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/sdcard/cm_wkdir/camp_match/src/camp_match/modules/payment/adapters/api/router.py", line 30, in initiate_payment
    result = await use_case.execute(
             ^^^^^^^^^^^^^^^^^^^^^^^
    ...<6 lines>...
    )
    ^
  File "/sdcard/cm_wkdir/camp_match/src/camp_match/modules/payment/application/use_cases/initiate_payment.py", line 74, in execute
    raise BookingNotEligibleForPayment("Booking is not awaiting payment or hold has expired.")
camp_match.modules.payment.application.errors.BookingNotEligibleForPayment: Booking is not awaiting payment or hold has expired.