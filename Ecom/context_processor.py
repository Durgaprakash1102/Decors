def base_template(request):
    if request.user.is_authenticated:
        if request.user.role == "admin":
            return {
                "base_template": "includes/sidebar.html"
            }
        else:
            return {
                "base_template": "base.html"
            }

    return {
        "base_template": "base.html"
    }