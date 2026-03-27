"""盒马自动化工具共享常量"""
from __future__ import annotations

# ── Android Keycodes ─────────────────────────────────
KEYCODE_BACK = 4
KEYCODE_HOME = 3
KEYCODE_ENTER = 66

# ── 盒马 APP ────────────────────────────────────────
HEMA_PACKAGE = "com.wudaokou.hippo"

# ── 盒马 Resource IDs ───────────────────────────────
RID_HOME_LOCATION_LAYOUT = "com.wudaokou.hippo:id/home_page_titlebar_location_layout"
RID_HOME_LOCATION_TEXT = "com.wudaokou.hippo:id/home_page_titlebar_location_text"
RID_SEARCH_EDITTEXT = "com.wudaokou.hippo:id/search_edittext"
RID_SEARCH_BUTTON = "com.wudaokou.hippo:id/search_button_text"
RID_SEARCH_BOX = "com.wudaokou.hippo:id/search_box"
RID_CART_ICON = "com.wudaokou.hippo:id/cart_icon"
RID_CART_BADGE = "com.wudaokou.hippo:id/tv_badge_count_hint"
RID_CART_ICON_LAYOUT = "com.wudaokou.hippo:id/search_cart_icon_layout"
RID_PRODUCT_CARD = "com.wudaokou.hippo:id/scene_root_view-hm_search_goods_item_line_simple"
RID_SELECT_ADDRESS_EDIT = "com.wudaokou.hippo:id/select_address_edit"
RID_ADDRESS_TITLE = "com.wudaokou.hippo:id/title"

# 弹窗关闭按钮
RID_CLOSE_BUTTONS = [
    "com.wudaokou.hippo:id/uikit_menu_close",
    "com.wudaokou.hippo:id/iv_close",
    "com.wudaokou.hippo:id/close",
    "com.wudaokou.hippo:id/btn_close",
]
CLOSE_BUTTON_TEXTS = ["我知道了", "知道了", "关闭", "取消", "不再提醒"]

# ── UI 解析阈值 ──────────────────────────────────────
MAX_VISIBLE_PRODUCTS = 10
MIN_PRODUCT_NAME_LENGTH = 3
FALLBACK_Y_PROXIMITY_PX = 300

# ── 等待时间 (秒) ────────────────────────────────────
APP_SPLASH_WAIT = 6.0
PAGE_LOAD_DELAY = 2.0
UI_SETTLE_DELAY = 0.3
TAP_INTERVAL = 0.6
CART_VERIFY_DELAY = 0.8
