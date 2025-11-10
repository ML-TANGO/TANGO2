DELIMITER $$

CREATE TRIGGER node_delete_trigger
BEFORE DELETE ON `node`
FOR EACH ROW
BEGIN
    DECLARE v_instance_id INT;
    DECLARE v_instance_allocate INT;
    
    DECLARE done INT DEFAULT 0;
    
    -- Declare cursor for selecting instance_id and instance_allocate for deleted node_id
    DECLARE cur CURSOR FOR 
    SELECT instance_id, instance_allocate
    FROM node_instance
    WHERE node_id = OLD.id;
    
    -- Declare handler for end of cursor
    DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = 1;
    
    -- Open cursor
    OPEN cur;
    
    -- Loop through all records related to deleted node
    read_loop: LOOP
        FETCH cur INTO v_instance_id, v_instance_allocate;
        IF done THEN
            LEAVE read_loop;
        END IF;
        
        -- Update instance_count in instance table, ensuring it doesn't go below zero
        UPDATE instance
        SET instance_count = GREATEST(instance_count - v_instance_allocate, 0)
        WHERE id = v_instance_id;
        
        -- Delete instance if instance_count becomes zero
        DELETE FROM instance
        WHERE id = v_instance_id AND instance_count = 0;
    END LOOP;
    
    -- Close cursor
    CLOSE cur;
END$$

DELIMITER ;
