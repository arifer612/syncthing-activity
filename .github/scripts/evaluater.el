;; evaluater.el
;; Author: Arif Er <arifer612@pm.me>
;; Description: Evaluates all source blocks and tangles the file

;; Code:
(require 'org)
(require 'ob-shell)
(require 'ob-python)

(setq org-confirm-babel-evaluate 'nil
      org-babel-python-command "python3")

(message "Starting evaluations.")
(find-file "README.org")
(org-babel-execute-buffer)
((lambda ()
  (interactive)
  (save-excursion
    (goto-char (point-min))
    (while (re-search-forward "\\(begin\\|end\\)_\\(example\\|src\\)" nil t)
      (replace-match (upcase (match-string 0)) t)))))
(save-buffer)
(message "Evaluation complete, README file updated.")

;; End of code
