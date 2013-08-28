$(document).ready(function () {
    if ($.fn.dataTableExt) {
        $.extend($.fn.dataTableExt.oSort, {
            "date-euro-anchor-pre": function (a) {
                if ($.trim($(a).html()) != '') {
                    var frDatea = $.trim($(a).html()).split(' ');
                    var frTimea = frDatea[1].split(':');
                    var frDatea2 = frDatea[0].split('\.');
                    var x = (frDatea2[2] + frDatea2[1] + frDatea2[0] + frTimea[0] + frTimea[1]) * 1;
                } else {
                    var x = 10000000000000; // = l'an 1000 ...
                }

                return x;
            },

            "date-euro-anchor-asc": function (a, b) {
                return a - b;
            },

            "date-euro-anchor-desc": function (a, b) {
                return b - a;
            }
        });

        $.extend($.fn.dataTableExt.oSort, {
            "date-euro-pre": function (a) {
                if ($.trim(a) != '') {
                    var frDatea = $.trim(a).split(' ');
                    var frTimea = frDatea[1].split(':');
                    var frDatea2 = frDatea[0].split('\.');
                    var x = (frDatea2[2] + frDatea2[1] + frDatea2[0] + frTimea[0] + frTimea[1]) * 1;
                } else {
                    var x = 10000000000000; // = l'an 1000 ...
                }

                return x;
            },

            "date-euro-asc": function (a, b) {
                return a - b;
            },

            "date-euro-desc": function (a, b) {
                return b - a;
            }
        });
    }
});