document.addEventListener('DOMContentLoaded', function() {
    // Handle parent checkbox change
    document.querySelectorAll('.multi-select > ul > li > input[type="checkbox"]').forEach(function(parentCheckbox) {
        parentCheckbox.addEventListener('change', function() {
            var subItemsContainer = this.parentNode.querySelector('.sub-items');
            if (subItemsContainer) {
                // Display sub-items if parent is checked
                subItemsContainer.style.display = this.checked ? 'block' : 'none';
                // Deselect all sub-items if parent is deselected
                if (!this.checked) {
                    subItemsContainer.querySelectorAll('input[type="checkbox"]').forEach(function(subCheckbox) {
                        subCheckbox.checked = false;
                    });
                }
            }
        });
    });

    // Handle click on the toggle sublist arrows
    document.querySelectorAll('.toggle-sublist').forEach(function(toggle) {
        toggle.addEventListener('click', function() {
            var sublist = this.parentNode.querySelector('.sub-items');
            var isExpanded = sublist.style.display === 'block';
            // Toggle the display of the sublist
            sublist.style.display = isExpanded ? 'none' : 'block';
            // Change the direction of the arrow based on the state
            this.textContent = isExpanded ? '►' : '▼';
        });
    });
});