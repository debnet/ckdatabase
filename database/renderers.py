from rest_framework.renderers import AdminRenderer, BrowsableAPIRenderer


class AdminRendererWithoutForms(AdminRenderer):
    def get_rendered_html_form(self, data, view, method, request):
        return None


class BrowsableAPIRendererWithoutForms(BrowsableAPIRenderer):
    def get_rendered_html_form(self, data, view, method, request):
        return None
