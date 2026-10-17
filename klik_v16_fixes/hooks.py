app_name = "klik_v16_fixes"
app_title = "KLiK v16 Fixes"
app_publisher = "klik_v16_fixes contributors"
app_description = "Runtime fixes for KLiK PoS on Frappe/ERPNext v16, without editing klik_pos"
app_email = "noreply@example.com"
app_license = "agpl-3.0"

# Apps
# ------------------

required_apps = ["klik_pos"]

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "klik_v16_fixes",
# 		"logo": "/assets/klik_v16_fixes/logo.png",
# 		"title": "KLiK v16 Fixes",
# 		"route": "/klik_v16_fixes",
# 		"has_permission": "klik_v16_fixes.api.permission.has_app_permission",
# 	}
# ]

# The dock, the rail down the left of the desk, is a document rather than a hook. Author it in
# Manage Dock on a developer-mode site and press Export to App, and it is written to
# `klik_v16_fixes/dock/klik_v16_fixes/klik_v16_fixes.json` for git to carry. An app that ships none has no
# rail: its sidebar gets a switcher in the header instead.
#
# A companion app, one that extends a host app rather than standing on its own, says so with
# `mount_on` on that same record, and its entries are appended to the host's rail. Mounting keeps
# the companion off the apps screen, so it takes precedence over any add_to_apps_screen above.

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/klik_v16_fixes/css/klik_v16_fixes.css"
# app_include_js = "/assets/klik_v16_fixes/js/klik_v16_fixes.js"

# include js, css files in header of web template
# web_include_css = "/assets/klik_v16_fixes/css/klik_v16_fixes.css"
# web_include_js = "/assets/klik_v16_fixes/js/klik_v16_fixes.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "klik_v16_fixes/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_kanban_js = {"doctype" : "public/js/doctype_kanban.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "klik_v16_fixes/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "klik_v16_fixes.utils.jinja_methods",
# 	"filters": "klik_v16_fixes.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "klik_v16_fixes.install.before_install"
# after_install = "klik_v16_fixes.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "klik_v16_fixes.uninstall.before_uninstall"
# after_uninstall = "klik_v16_fixes.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "klik_v16_fixes.utils.before_app_install"
# after_app_install = "klik_v16_fixes.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "klik_v16_fixes.utils.before_app_uninstall"
# after_app_uninstall = "klik_v16_fixes.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "klik_v16_fixes.build.after_build"

# To hook into the build process of other apps
# The list of apps being built is passed as an argument

# after_app_build = "klik_v16_fixes.build.after_app_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "klik_v16_fixes.notifications.get_notification_config"

# Awesome Bar
# -----------
# Extra search results: list of dicts with label, description, route, index.
# route: ["List", "ToDo"], "/desk/docs/some/page", or "https://example.com"
# awesomebar_search = ["klik_v16_fixes.search.awesomebar_results"]

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"klik_v16_fixes.tasks.all"
# 	],
# 	"daily": [
# 		"klik_v16_fixes.tasks.daily"
# 	],
# 	"hourly": [
# 		"klik_v16_fixes.tasks.hourly"
# 	],
# 	"weekly": [
# 		"klik_v16_fixes.tasks.weekly"
# 	],
# 	"monthly": [
# 		"klik_v16_fixes.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "klik_v16_fixes.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "klik_v16_fixes.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# Roll back a checkout that fails part-way through submit (see checkout.py)
override_whitelisted_methods = {
	"klik_pos.api.sales_invoice.queue_sales_invoice": "klik_v16_fixes.checkout.queue_sales_invoice",
	"klik_pos.api.sales_invoice.create_and_submit_invoice": "klik_v16_fixes.checkout.create_and_submit_invoice",
}
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "klik_v16_fixes.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# Runtime fixes, installed once per process (see catalogue.py, pricing.py and closing.py)
before_request = ["klik_v16_fixes.catalogue.apply", "klik_v16_fixes.pricing.apply", "klik_v16_fixes.closing.apply"]
# Blind shift close script for the /klik_pos page (see blind_close.py)
after_request = ["klik_v16_fixes.blind_close.inject_into_klik_page"]

# Job Events
# ----------
before_job = ["klik_v16_fixes.catalogue.apply", "klik_v16_fixes.pricing.apply", "klik_v16_fixes.closing.apply"]
# after_job = ["klik_v16_fixes.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"klik_v16_fixes.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

