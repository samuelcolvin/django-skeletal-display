from django.shortcuts import redirect
import django.views.generic as generic
import settings
import SkeletalDisplay, HotDjango
from django.core.urlresolvers import reverse

class Authenticated(object):
    def dispatch(self, request, *args, **kwargs):
        if settings.LOGIN_REQUIRED and not request.user.is_authenticated():
            return redirect(reverse('login'))
        return super(Authenticated, self).dispatch(request, *args, **kwargs)
    
class ViewBase(Authenticated):
    side_menu = True
    all_auth_permitted = False
    extra_permission_check = False
    viewname = 'sk'
    include_appname_in_args = True
    include_model_in_args = True
    base_name = 'Model Display'
    
    def get(self, request, *args, **kw):
        self.setup_context(**kw)
        if not self.check_permissions():
            return redirect(reverse('permission_denied'))
        return super(ViewBase, self).get(request, *args, **kw)
    
    def check_permissions(self):
        if self.all_auth_permitted or self.is_allowed():
            return True
        if self.extra_permission_check and self.has_extra_permission():
            return True
        return False
    
    def setup_context(self, **kw):
        self._apps = SkeletalDisplay.get_display_apps()
        self._disp_model = None
        self._app_name = kw.get('app', None)
        self._model_name = kw.get('model', None)
        self._item_id = kw.get('id', None)
        if None not in (self._app_name, self._model_name):
            self._disp_model = self._get_model(self._app_name, self._model_name)
            self._plural_t = get_plural_name(self._disp_model)
            self._single_t = get_single_name(self._disp_model)
            if self._item_id is not None:
                self._item = self._disp_model.model.objects.get(id = int(self._item_id))
        
        if not hasattr(self, '_context'):
            self._context={}
        self.create_crums()
        if self.side_menu:
            self._generate_side_menu()
        top_active = None
        if hasattr(self, 'top_active'):
            top_active = self.top_active
        self._context.update(basic_context(self.request, top_active))
        
    def is_allowed(self):
        return HotDjango.is_allowed_hot(self.request.user)
    
    def _get_model(self, app_name, model_name):
        try:
            return self._apps[app_name][model_name]
        except:
            raise Exception('ERROR: %s.%s not found' % (app_name, model_name))
    
    def set_links(self):
        links =[]
        if self._disp_model.addable:
            links.append({'url': reverse('add_item', args=[self._app_name, self._model_name]), 'name': 'Add ' + self._single_t})
        return links
    
    def set_crums(self, set_to = None, add = None):
        if not self._disp_model.show_crums:
            del self.request.session['crums']
            return
        if set_to is not None:
            self.request.session['crums'] = set_to
        if add is not None:
            if 'crums' not in self.request.session or len(self.request.session['crums']) == 0:
                self.request.session['crums'] = add
            elif add[0] != self.request.session['crums'][-1]:
                self.request.session['crums'] += add
        self._context['crums'] = self.request.session['crums']
        
    def create_crums(self):
        if self._disp_model is not None and self._disp_model.display:
            crums=[{'url': reverse(self.viewname), 'name': self.base_name}]
            crums.append({'url': reverse(self.viewname, args=self.args_base(model=self._model_name)), 'name' : self._plural_t})
            self.set_crums(set_to = crums)

    def _generate_side_menu(self):
        side_menu = []
        active = None
        if self._disp_model is not None: active = self._disp_model.__name__
        for app_name in self._apps:
            for model_name in self._apps[app_name]:
                if hasattr(self, 'side_menu_items') and model_name not in self.side_menu_items:
                    continue
                model = self._apps[app_name][model_name]
                if model.display:
                    cls = ''
                    if model_name == active: cls = 'open'
                    side_menu.append({'url': reverse(self.viewname, args=self.args_base(app_name, model_name)), 
                                    'name': get_plural_name(model), 'class': cls, 'index': model.index})
        side_menu = sorted(side_menu, key=lambda d: d['index'])
        self._context['side_menu'] = side_menu
    
    def args_base(self, app=None, model=None):
        if app is None:
            app = self._app_name
        args = []
        if self.include_appname_in_args:
            args = [app]
        if model is not None and self.include_model_in_args:
            args.append(model)
        return args
    
    def generate_table(self, table, queryset):
        return table(queryset, viewname=self.viewname, reverse_args=self.args_base(), apps=self._apps)#, use_model_arg = False

class TemplateBase(ViewBase, generic.TemplateView):
    pass

class PermissionDenied(ViewBase, generic.TemplateView):
    template_name = 'sk_simple_message.html'
    side_menu = False
    all_auth_permitted = True
    
    def get(self, request, *args, **kw):
        self.setup_context(**kw)
        return super(PermissionDenied, self).get(request, *args, **kw)

    def get_context_data(self, **kw):
        self._context['main_message'] = 'You do not have Permission to view this page.'
        return self._context

def get_plural_name(dm):
    return  unicode(dm.model._meta.verbose_name_plural)

def get_single_name(dm):
    return  unicode(dm.model._meta.verbose_name)

def basic_context(request, top_active = None):
    if top_active is not None:
        request.session['top_active'] = top_active
    elif 'top_active' in request.session:
        top_active = request.session['top_active']
    context = {}
    if 'message' in request.session:
        context['info'] = request.session.pop('info')
    if 'success' in request.session:
        context['success'] = request.session.pop('success')
    if 'errors' in request.session:
        context['errors'] = request.session.pop('errors')
    context['base_template'] = 'sk_page_base.html'
    if hasattr(settings, 'PAGE_BASE'):
        context['base_template'] = settings.PAGE_BASE

    raw_menu = []
    for item in settings.TOP_MENU:
        if 'groups' in item:
            if HotDjango.is_allowed_hot(request.user, permitted_groups=item['groups']):
                raw_menu.append(item)
        else:
            raw_menu.append(item)
    raw_menu.append({'url': 'user_profile', 'name': 'Account'})
    if request.user.is_staff:
        raw_menu.append({'url': 'admin:index', 'name': 'Staff Admin'})
    top_menu = []
    for item in raw_menu:
        menu_item = {'url': reverse(item['url']), 'name': item['name']}
        if item['url'] == top_active:
            menu_item['class'] = 'active'
        top_menu.append(menu_item)
    
    context['top_menu'] = top_menu
    context['site_title'] = settings.SITE_TITLE
    return context











