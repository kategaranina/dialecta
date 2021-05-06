(function($) {
    $(document).ready(function() {
        var search_div = $('#search');
        if (search_div) {
            var search_url = document.URL + 'search';
            $.ajax({
                url: search_url,
                success: function() {
                    search_div.prepend('<a href="' + search_url + '" class="grp-button" id="search_button">Advanced search</a>');
                }
            });
        };
    });
})(grp.jQuery);
