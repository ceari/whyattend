/**
 * jquery.confirm
 * @author My C-Labs
 * @author Matthieu Napoli <matthieu@mnapoli.fr>
 * @url https://github.com/myclabs/jquery.confirm
 * Modified by [WHY]fantastico for Bootstrap 3 / WoT Attendance Tracker
 */
(function($) {

	/**
	 * Confirm a link or a button
	 * @param options {text, confirm, cancel, confirmButton, cancelButton, post}
	 */
	$.fn.confirm = function(options) {
		if (typeof options === 'undefined') {
			options = {};
		}

		options.button = $(this);

		this.click(function(e) {
			e.preventDefault();

			$.confirm(options);
		});

		return this;
	};

	/**
	 * Show a confirmation dialog
	 * @param options {text, confirm, cancel, confirmButton, cancelButton, post}
	 */
	$.confirm = function(options) {
		// Options
		if (typeof options === 'undefined') {
			options = {};
		}
        if (typeof options.title === 'undefined') {
			options.title = "Are you sure?";
		}
		if (typeof options.text === 'undefined') {
			options.text = "Are you sure?";
		}
		if (typeof options.confirmButton === 'undefined') {
			options.confirmButton = "Yes";
		}
		if (typeof options.cancelButton === 'undefined') {
			options.cancelButton = "Cancel";
		}
		if (typeof options.post === 'undefined') {
			options.post = false;
		}
		if (typeof options.confirm === 'undefined') {
			options.confirm = function(o) {
				var url = o.attr('href');
				if (options.post) {
					var form = $('<form method="post" class="hide" action="' + url + '"></form>');
					$("body").append(form);
					form.submit();
				} else {
					window.location = url;
				}
			};
		}
		if (typeof options.cancel === 'undefined') {
			options.cancel = function(o) {
                $('#myModal').modal('hide');
			};
		}
		if (typeof options.button === 'undefined') {
			options.button = null;
		}

		// Modal
		var buttons = '<button class="confirm btn btn-primary" type="button" data-toggle="modal">'
			+ options.confirmButton + '</button>'
			+ '<button class="cancel btn" type="button" data-dismiss="modal">'
			+ options.cancelButton + '</button>';
		var modalHTML = '<div class="modal fade" id="myModal" tabindex="-1" role="dialog" aria-labelledby="myModalLabel" aria-hidden="true">'
            + '<div class="modal-dialog">'
            + '<div class="modal-content">'
            + '<div class="modal-header">'+options.title+'</div>'
			+ '<div class="modal-body">' + options.text + '</div>'
			+ '<div class="modal-footer">' + buttons + '</div>'
			+ '</div></div></div>';

		var modal = $(modalHTML);

		modal.on('shown', function() {
			modal.find(".btn-primary:first").focus();
		});
		modal.on('hidden', function() {
			modal.remove();
		});
		modal.find(".confirm").click(function(e) {
			options.confirm(options.button);
		});
		modal.find(".cancel").click(function(e) {
			options.cancel(options.button);
		});

		// Show the modal
		$("body").append(modal);
		modal.modal();
	}

})(jQuery);
