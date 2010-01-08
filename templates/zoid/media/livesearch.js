/* jQuery live search
 * Heavily based on Zope jQuery Live Search by Roger Ineichen
 * http://svn.zope.org/jquery.livesearch/trunk/src/jquery/livesearch/jquery.livesearch.js
 */

function setLiveSearchResult(data, status) {
    // we use a default element id, use a custom callback if this doesn't fit
    ele = $('#results');
     $(ele).html(data);

}

//----------------------------------------------------------------------------
// public API
//----------------------------------------------------------------------------
/**
 * apply live search functionality. *
 * @example  $("#myInputField").jsonLiveSearch({url:'http://localhost/page/'});
 */
jQuery.fn.jsonLiveSearch = function(settings) {
    settings = jQuery.extend({
        jsonURL: contextURL,
        callback: setLiveSearchResult
    }, settings);
    return this.each(function(){
        $(this).keyup(function(){
        	value = $(this).val();
			jQuery.get(jsonURL + value, setLiveSearchResult)
        });

    });
};